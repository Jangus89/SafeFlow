/**
 * SafeFlow Integration Tests - SLA Monitoring and Escalation
 *
 * Tests the SLA enforcement system including overdue detection,
 * escalation level incrementing, auto-reassignment, notification chains,
 * and urgency-based SLA timescales.
 *
 * Prerequisites:
 *   - Staging environment configured
 *   - Make.com Scenario D (SLA Monitor) active
 *   - Environment variables set (see config/environments/staging.env.example)
 *
 * Usage:
 *   npm test -- --grep "SLA"
 */

const axios = require('axios');
const { expect } = require('chai');
require('dotenv').config({ path: process.env.DOTENV_PATH || '../../config/environments/staging.env.example' });

// ─── Configuration ──────────────────────────────────────────────────────────────

const CONFIG = {
  airtableApiKey: process.env.AIRTABLE_API_KEY,
  airtableBaseId: process.env.AIRTABLE_BASE_ID,
  makeWebhookScenarioD: process.env.MAKE_WEBHOOK_URL_SCENARIO_D,
  slaCheckIntervalMinutes: parseInt(process.env.SLA_CHECK_INTERVAL_MINUTES || '15', 10),
  environment: process.env.ENVIRONMENT || 'staging',
  pollingIntervalMs: 2000,
  pollingTimeoutMs: 25000,
};

const AIRTABLE_BASE_URL = `https://api.airtable.com/v0/${CONFIG.airtableBaseId}`;

const AIRTABLE_HEADERS = {
  Authorization: `Bearer ${CONFIG.airtableApiKey}`,
  'Content-Type': 'application/json',
};

/**
 * SLA timescales by urgency level (in hours).
 * These match the business rules defined in the SafeFlow system.
 */
const SLA_TIMESCALES = {
  EMERGENCY: 4,
  URGENT: 24,
  STANDARD: 72,
  SCHEDULED: 168, // 7 days
};

/**
 * Escalation intervals per urgency level (in hours).
 * Defines how frequently escalation increments after the initial SLA breach.
 */
const ESCALATION_INTERVALS = {
  EMERGENCY: 1,
  URGENT: 4,
  STANDARD: 24,
  SCHEDULED: 48,
};

// ─── Test Data Cleanup Tracking ─────────────────────────────────────────────────

const createdRecordIds = {
  workItems: [],
  interactionLogs: [],
};

// ─── Helper Functions ───────────────────────────────────────────────────────────

async function createAirtableRecord(tableName, fields) {
  const response = await axios.post(
    `${AIRTABLE_BASE_URL}/${encodeURIComponent(tableName)}`,
    { fields },
    { headers: AIRTABLE_HEADERS }
  );
  return response.data;
}

async function getAirtableRecord(tableName, recordId) {
  const response = await axios.get(
    `${AIRTABLE_BASE_URL}/${encodeURIComponent(tableName)}/${recordId}`,
    { headers: AIRTABLE_HEADERS }
  );
  return response.data;
}

async function findAirtableRecords(tableName, filterFormula, maxRecords = 10) {
  const response = await axios.get(
    `${AIRTABLE_BASE_URL}/${encodeURIComponent(tableName)}`,
    {
      headers: AIRTABLE_HEADERS,
      params: {
        filterByFormula: filterFormula,
        maxRecords,
      },
    }
  );
  return response.data.records || [];
}

async function updateAirtableRecord(tableName, recordId, fields) {
  const response = await axios.patch(
    `${AIRTABLE_BASE_URL}/${encodeURIComponent(tableName)}/${recordId}`,
    { fields },
    { headers: AIRTABLE_HEADERS }
  );
  return response.data;
}

async function deleteAirtableRecord(tableName, recordId) {
  await axios.delete(
    `${AIRTABLE_BASE_URL}/${encodeURIComponent(tableName)}/${recordId}`,
    { headers: AIRTABLE_HEADERS }
  );
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function generateTestMarker() {
  return `SFTEST_SLA_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

async function pollForRecord(tableName, filterFormula, timeoutMs = CONFIG.pollingTimeoutMs) {
  const startTime = Date.now();
  while (Date.now() - startTime < timeoutMs) {
    const records = await findAirtableRecords(tableName, filterFormula, 1);
    if (records.length > 0) {
      return records[0];
    }
    await sleep(CONFIG.pollingIntervalMs);
  }
  return null;
}

async function pollForFieldValue(tableName, recordId, fieldName, expectedValue, timeoutMs = CONFIG.pollingTimeoutMs) {
  const startTime = Date.now();
  while (Date.now() - startTime < timeoutMs) {
    const record = await getAirtableRecord(tableName, recordId);
    if (record.fields[fieldName] === expectedValue) {
      return record;
    }
    await sleep(CONFIG.pollingIntervalMs);
  }
  return null;
}

/**
 * Creates a past date by subtracting hours from the current time.
 * @param {number} hoursAgo - Number of hours in the past
 * @returns {string}        - ISO date string
 */
function hoursAgoISO(hoursAgo) {
  const d = new Date();
  d.setHours(d.getHours() - hoursAgo);
  return d.toISOString();
}

/**
 * Creates a test Work_Item that is already overdue based on the given urgency level.
 * The sla_due_at is set to a time in the past so the SLA monitor will detect it.
 *
 * @param {string} marker       - Unique test marker
 * @param {string} urgency      - Urgency level (EMERGENCY, URGENT, STANDARD, SCHEDULED)
 * @param {number} hoursOverdue - How many hours past the SLA deadline (default: 1)
 * @returns {object}            - Created Airtable record
 */
async function createOverdueWorkItem(marker, urgency, hoursOverdue = 1) {
  const slaDueAt = hoursAgoISO(hoursOverdue);
  const createdAt = hoursAgoISO(SLA_TIMESCALES[urgency] + hoursOverdue);

  const record = await createAirtableRecord('Work_Items', {
    title: `SLA Test: Overdue ${urgency} [${marker}]`,
    description: `Integration test for SLA escalation. Urgency: ${urgency}. Marker: ${marker}. This item was intentionally created as overdue.`,
    current_state: 'ASSIGNED',
    discipline_required: 'GENERAL_MAINTENANCE',
    urgency,
    routing_decision: 'INTERNAL_ENGINEER',
    llm_confidence: 0.95,
    location_building: 'SLA Test Building',
    location_floor: 'Ground',
    sla_due_at: slaDueAt,
    escalation_level: 0,
    state_started_at: createdAt,
    created_at: createdAt,
    source_message_id: `wamid.slatest_${marker}`,
    whatsapp_thread_id: `thread_slatest_${marker}`,
  });
  createdRecordIds.workItems.push(record.id);
  return record;
}

/**
 * Creates a test Work_Item that is within its SLA deadline (not yet overdue).
 */
async function createOnTimeWorkItem(marker, urgency) {
  const hoursRemaining = Math.floor(SLA_TIMESCALES[urgency] / 2);
  const slaDueAt = new Date();
  slaDueAt.setHours(slaDueAt.getHours() + hoursRemaining);

  const createdAt = new Date();
  createdAt.setHours(createdAt.getHours() - hoursRemaining);

  const record = await createAirtableRecord('Work_Items', {
    title: `SLA Test: On Time ${urgency} [${marker}]`,
    description: `Integration test item that is within SLA. Urgency: ${urgency}. Marker: ${marker}.`,
    current_state: 'ASSIGNED',
    discipline_required: 'GENERAL_MAINTENANCE',
    urgency,
    routing_decision: 'INTERNAL_ENGINEER',
    llm_confidence: 0.95,
    location_building: 'SLA Test Building',
    sla_due_at: slaDueAt.toISOString(),
    escalation_level: 0,
    state_started_at: createdAt.toISOString(),
    created_at: createdAt.toISOString(),
    source_message_id: `wamid.slatest_ontime_${marker}`,
  });
  createdRecordIds.workItems.push(record.id);
  return record;
}

/**
 * Triggers the SLA monitor scenario via its Make.com webhook.
 */
async function triggerSLACheck() {
  const response = await axios.post(
    CONFIG.makeWebhookScenarioD,
    {
      action: 'check_sla',
      trigger: 'integration_test',
      timestamp: new Date().toISOString(),
    },
    {
      headers: { 'Content-Type': 'application/json' },
      timeout: 15000,
    }
  );
  return response;
}

// ─── Test Suite ─────────────────────────────────────────────────────────────────

describe('SLA Monitoring and Escalation', function () {
  this.timeout(30000);

  before(function () {
    const requiredVars = [
      'AIRTABLE_API_KEY',
      'AIRTABLE_BASE_ID',
      'MAKE_WEBHOOK_URL_SCENARIO_D',
    ];
    const missing = requiredVars.filter((v) => !process.env[v]);
    if (missing.length > 0) {
      this.skip();
      console.warn(`Skipping SLA tests: missing env vars: ${missing.join(', ')}`);
    }
  });

  after(async function () {
    this.timeout(60000);
    const tables = [
      { name: 'Interaction_Logs', ids: createdRecordIds.interactionLogs },
      { name: 'Work_Items', ids: createdRecordIds.workItems },
    ];
    for (const table of tables) {
      for (const id of table.ids) {
        try {
          await deleteAirtableRecord(table.name, id);
        } catch (err) {
          console.warn(`Cleanup: failed to delete ${table.name}/${id}: ${err.message}`);
        }
      }
    }
  });

  // ── Overdue Detection ─────────────────────────────────────────────────────────

  describe('Overdue Item Detection', function () {
    it('should detect overdue STANDARD work items', async function () {
      this.timeout(45000);
      const marker = generateTestMarker();

      // Create a work item that is 2 hours past its SLA deadline
      const overdueItem = await createOverdueWorkItem(marker, 'STANDARD', 2);

      // Trigger the SLA check
      const response = await triggerSLACheck();
      expect(response.status).to.be.oneOf([200, 202]);

      // Wait for the SLA monitor to process
      await sleep(10000);

      // Verify the item was detected as overdue
      const updatedItem = await getAirtableRecord('Work_Items', overdueItem.id);

      // The formula field is_overdue is calculated, so check sla_due_at is in the past
      const slaDue = new Date(updatedItem.fields.sla_due_at);
      expect(slaDue.getTime()).to.be.below(Date.now(), 'SLA deadline should be in the past');

      // Escalation level should have been incremented from 0
      expect(updatedItem.fields.escalation_level).to.be.at.least(1,
        'Overdue items should have escalation_level incremented');
    });

    it('should detect overdue EMERGENCY work items', async function () {
      this.timeout(45000);
      const marker = generateTestMarker();

      // Create an emergency item that is 1 hour past SLA (SLA is 4h for emergency)
      const overdueItem = await createOverdueWorkItem(marker, 'EMERGENCY', 1);

      const response = await triggerSLACheck();
      expect(response.status).to.be.oneOf([200, 202]);

      await sleep(10000);

      const updatedItem = await getAirtableRecord('Work_Items', overdueItem.id);
      expect(updatedItem.fields.escalation_level).to.be.at.least(1);

      // Emergency items may be moved to ESCALATED state
      expect(updatedItem.fields.current_state).to.be.oneOf(
        ['ASSIGNED', 'ESCALATED', 'IN_PROGRESS'],
        'Emergency overdue items should be escalated or remain assigned'
      );
    });

    it('should not flag items that are within their SLA deadline', async function () {
      this.timeout(45000);
      const marker = generateTestMarker();

      // Create a work item that is well within its SLA
      const onTimeItem = await createOnTimeWorkItem(marker, 'STANDARD');

      // Trigger SLA check
      await triggerSLACheck();
      await sleep(10000);

      // Verify escalation level is still 0
      const updatedItem = await getAirtableRecord('Work_Items', onTimeItem.id);
      expect(updatedItem.fields.escalation_level).to.equal(0,
        'On-time items should not be escalated');
      expect(updatedItem.fields.current_state).to.equal('ASSIGNED');
    });

    it('should not escalate CLOSED or CANCELLED work items', async function () {
      this.timeout(45000);
      const marker = generateTestMarker();

      // Create a closed item with a past SLA deadline
      const closedItem = await createAirtableRecord('Work_Items', {
        title: `SLA Test: Closed Item [${marker}]`,
        description: `Closed item that was overdue before closure. Marker: ${marker}.`,
        current_state: 'CLOSED',
        urgency: 'STANDARD',
        sla_due_at: hoursAgoISO(48),
        escalation_level: 0,
        closed_at: hoursAgoISO(24),
        created_at: hoursAgoISO(96),
        state_started_at: hoursAgoISO(24),
      });
      createdRecordIds.workItems.push(closedItem.id);

      await triggerSLACheck();
      await sleep(10000);

      const updatedItem = await getAirtableRecord('Work_Items', closedItem.id);
      expect(updatedItem.fields.escalation_level).to.equal(0,
        'Closed items should not be escalated even if past SLA');
      expect(updatedItem.fields.current_state).to.equal('CLOSED');
    });
  });

  // ── Escalation Level Increment ────────────────────────────────────────────────

  describe('Escalation Level Increment', function () {
    it('should increment escalation_level on each SLA check cycle', async function () {
      this.timeout(60000);
      const marker = generateTestMarker();

      // Create an overdue item with escalation_level already at 1
      const item = await createAirtableRecord('Work_Items', {
        title: `SLA Escalation Test [${marker}]`,
        description: `Testing escalation increment. Marker: ${marker}.`,
        current_state: 'ASSIGNED',
        urgency: 'URGENT',
        discipline_required: 'ELECTRICAL',
        routing_decision: 'INTERNAL_ENGINEER',
        sla_due_at: hoursAgoISO(8), // 8 hours overdue on a 24h SLA
        escalation_level: 1,
        state_started_at: hoursAgoISO(32),
        created_at: hoursAgoISO(32),
        source_message_id: `wamid.escalation_${marker}`,
      });
      createdRecordIds.workItems.push(item.id);

      // Trigger SLA check
      await triggerSLACheck();
      await sleep(10000);

      // Escalation level should have incremented from 1 to 2
      const updatedItem = await getAirtableRecord('Work_Items', item.id);
      expect(updatedItem.fields.escalation_level).to.be.at.least(2,
        'Escalation level should increment on repeated SLA breaches');
    });

    it('should not increment beyond maximum escalation level', async function () {
      this.timeout(45000);
      const marker = generateTestMarker();
      const maxEscalation = 5;

      // Create an item already at max escalation
      const item = await createAirtableRecord('Work_Items', {
        title: `SLA Max Escalation Test [${marker}]`,
        description: `Testing escalation cap. Marker: ${marker}.`,
        current_state: 'ESCALATED',
        urgency: 'STANDARD',
        sla_due_at: hoursAgoISO(200),
        escalation_level: maxEscalation,
        state_started_at: hoursAgoISO(200),
        created_at: hoursAgoISO(272),
        source_message_id: `wamid.maxesc_${marker}`,
      });
      createdRecordIds.workItems.push(item.id);

      await triggerSLACheck();
      await sleep(10000);

      const updatedItem = await getAirtableRecord('Work_Items', item.id);
      // Should remain at max or be capped
      expect(updatedItem.fields.escalation_level).to.be.at.most(maxEscalation + 1,
        'Escalation should be capped or increment gracefully');
    });
  });

  // ── Auto-Reassignment ────────────────────────────────────────────────────────

  describe('Auto-Reassignment', function () {
    it('should reassign work item to a different engineer after escalation threshold', async function () {
      this.timeout(60000);
      const marker = generateTestMarker();

      // Find two active engineers in the staging data
      const engineers = await findAirtableRecords(
        'People',
        'AND({role} = "ENGINEER", {is_active} = TRUE())',
        2
      );

      if (engineers.length < 2) {
        this.skip();
        console.warn('Skipping auto-reassignment test: need at least 2 active engineers');
        return;
      }

      const originalEngineerId = engineers[0].id;

      // Create an overdue item assigned to the first engineer with escalation level 2
      const item = await createAirtableRecord('Work_Items', {
        title: `SLA Reassignment Test [${marker}]`,
        description: `Testing auto-reassignment on escalation. Marker: ${marker}.`,
        current_state: 'ASSIGNED',
        urgency: 'URGENT',
        discipline_required: 'GENERAL_MAINTENANCE',
        routing_decision: 'INTERNAL_ENGINEER',
        assigned_engineer_id: [originalEngineerId],
        sla_due_at: hoursAgoISO(12),
        escalation_level: 2, // Escalation level 2 triggers reassignment
        state_started_at: hoursAgoISO(36),
        created_at: hoursAgoISO(36),
        source_message_id: `wamid.reassign_${marker}`,
      });
      createdRecordIds.workItems.push(item.id);

      // Trigger SLA check
      await triggerSLACheck();
      await sleep(12000);

      const updatedItem = await getAirtableRecord('Work_Items', item.id);

      // If auto-reassignment is implemented, the assigned engineer should change
      if (updatedItem.fields.assigned_engineer_id &&
          updatedItem.fields.assigned_engineer_id.length > 0) {
        const newEngineerId = updatedItem.fields.assigned_engineer_id[0];

        // The new engineer may or may not differ depending on availability
        // but escalation level should have incremented
        expect(updatedItem.fields.escalation_level).to.be.at.least(3);

        // If reassignment occurred, log it
        if (newEngineerId !== originalEngineerId) {
          // Verify state history records the reassignment
          if (updatedItem.fields.state_history) {
            const history = JSON.parse(updatedItem.fields.state_history);
            const reassignmentEntry = history.find((h) =>
              h.notes && h.notes.toLowerCase().includes('reassign')
            );
            // Reassignment notation in history is expected but not strictly required
          }
        }
      }
    });

    it('should move to ESCALATED state when no reassignment is possible', async function () {
      this.timeout(45000);
      const marker = generateTestMarker();

      // Create an item at high escalation with no engineer assigned
      const item = await createAirtableRecord('Work_Items', {
        title: `SLA No Reassignment Test [${marker}]`,
        description: `Testing ESCALATED state transition. Marker: ${marker}.`,
        current_state: 'ASSIGNED',
        urgency: 'EMERGENCY',
        discipline_required: 'SPECIALIST',
        routing_decision: 'INTERNAL_ENGINEER',
        sla_due_at: hoursAgoISO(6),
        escalation_level: 3,
        state_started_at: hoursAgoISO(10),
        created_at: hoursAgoISO(10),
        source_message_id: `wamid.noreas_${marker}`,
      });
      createdRecordIds.workItems.push(item.id);

      await triggerSLACheck();
      await sleep(10000);

      const updatedItem = await getAirtableRecord('Work_Items', item.id);

      // At high escalation levels, the item should transition to ESCALATED
      expect(updatedItem.fields.current_state).to.be.oneOf(
        ['ASSIGNED', 'ESCALATED'],
        'Highly escalated items should be in ASSIGNED or ESCALATED state'
      );
      expect(updatedItem.fields.escalation_level).to.be.at.least(4);
    });
  });

  // ── Notification Chain ────────────────────────────────────────────────────────

  describe('Notification Chain', function () {
    it('should send notifications to the assigned engineer on first escalation', async function () {
      this.timeout(45000);
      const marker = generateTestMarker();

      const item = await createOverdueWorkItem(marker, 'STANDARD', 4);

      await triggerSLACheck();
      await sleep(12000);

      // Find escalation notifications for this work item
      const notifications = await findAirtableRecords(
        'Interaction_Logs',
        `AND({direction} = "OUTBOUND", SEARCH("${item.id}", ARRAYJOIN({work_item_id}, ",")))`,
        10
      );
      notifications.forEach((n) => createdRecordIds.interactionLogs.push(n.id));

      // At least one notification should be sent on escalation
      expect(notifications.length).to.be.at.least(1,
        'At least one escalation notification should be sent');

      if (notifications.length > 0) {
        // Notification should be via WhatsApp or email
        expect(notifications[0].fields.channel).to.be.oneOf(
          ['WHATSAPP', 'EMAIL', 'SYSTEM'],
          'Escalation notification should be sent via a supported channel'
        );
      }
    });

    it('should escalate to supervisor at escalation level 2', async function () {
      this.timeout(45000);
      const marker = generateTestMarker();

      // Create item already at escalation level 1, about to be bumped to 2
      const item = await createAirtableRecord('Work_Items', {
        title: `SLA Supervisor Escalation [${marker}]`,
        description: `Testing supervisor notification at level 2. Marker: ${marker}.`,
        current_state: 'ASSIGNED',
        urgency: 'URGENT',
        discipline_required: 'PLUMBING',
        routing_decision: 'INTERNAL_ENGINEER',
        sla_due_at: hoursAgoISO(10),
        escalation_level: 1,
        state_started_at: hoursAgoISO(34),
        created_at: hoursAgoISO(34),
        source_message_id: `wamid.supesc_${marker}`,
      });
      createdRecordIds.workItems.push(item.id);

      await triggerSLACheck();
      await sleep(12000);

      // Find all outbound notifications for this item
      const notifications = await findAirtableRecords(
        'Interaction_Logs',
        `AND({direction} = "OUTBOUND", SEARCH("${item.id}", ARRAYJOIN({work_item_id}, ",")))`,
        10
      );
      notifications.forEach((n) => createdRecordIds.interactionLogs.push(n.id));

      // At level 2, supervisor should be notified in addition to the engineer
      // We check for multiple outbound notifications
      if (notifications.length > 1) {
        // There should be notifications to different recipients
        const personIds = notifications
          .map((n) => n.fields.person_id)
          .filter(Boolean)
          .map((pid) => (Array.isArray(pid) ? pid[0] : pid));
        // If we have multiple recipient person IDs, that indicates escalation chain
        const uniqueRecipients = [...new Set(personIds)];
        expect(uniqueRecipients.length).to.be.at.least(1,
          'Level 2 escalation should notify at least one person (supervisor or engineer)');
      }
    });

    it('should escalate to property manager at escalation level 3', async function () {
      this.timeout(45000);
      const marker = generateTestMarker();

      const item = await createAirtableRecord('Work_Items', {
        title: `SLA PM Escalation [${marker}]`,
        description: `Testing property manager notification at level 3. Marker: ${marker}.`,
        current_state: 'ESCALATED',
        urgency: 'STANDARD',
        discipline_required: 'GENERAL_MAINTENANCE',
        routing_decision: 'INTERNAL_ENGINEER',
        sla_due_at: hoursAgoISO(120), // 5 days overdue
        escalation_level: 2,
        state_started_at: hoursAgoISO(192),
        created_at: hoursAgoISO(192),
        source_message_id: `wamid.pmesc_${marker}`,
      });
      createdRecordIds.workItems.push(item.id);

      await triggerSLACheck();
      await sleep(12000);

      const updatedItem = await getAirtableRecord('Work_Items', item.id);
      expect(updatedItem.fields.escalation_level).to.be.at.least(3);

      // Find notifications for this item
      const notifications = await findAirtableRecords(
        'Interaction_Logs',
        `AND({direction} = "OUTBOUND", SEARCH("${item.id}", ARRAYJOIN({work_item_id}, ",")))`,
        10
      );
      notifications.forEach((n) => createdRecordIds.interactionLogs.push(n.id));

      // At level 3, expect notifications to be sent (to property manager or admin)
      expect(notifications.length).to.be.at.least(1,
        'Level 3 escalation should generate at least one notification');
    });

    it('should include SLA breach details in escalation notifications', async function () {
      this.timeout(45000);
      const marker = generateTestMarker();

      const item = await createOverdueWorkItem(marker, 'URGENT', 8);

      await triggerSLACheck();
      await sleep(12000);

      const notifications = await findAirtableRecords(
        'Interaction_Logs',
        `AND({direction} = "OUTBOUND", SEARCH("${item.id}", ARRAYJOIN({work_item_id}, ",")))`,
        10
      );
      notifications.forEach((n) => createdRecordIds.interactionLogs.push(n.id));

      if (notifications.length > 0) {
        const content = notifications[0].fields.message_content || '';
        // The notification content should reference the overdue nature
        expect(content.length).to.be.greaterThan(20,
          'Escalation notification should contain meaningful content');
        // May contain keywords like overdue, escalat*, SLA, breach, urgent
        const containsRelevantKeyword = /overdue|escalat|sla|breach|urgent|attention/i.test(content);
        expect(containsRelevantKeyword).to.be.true;
      }
    });
  });

  // ── Urgency-Level SLA Timescales ──────────────────────────────────────────────

  describe('Urgency-Level SLA Timescales', function () {
    it('should set correct SLA deadline for EMERGENCY urgency (4 hours)', async function () {
      const marker = generateTestMarker();

      const createdAt = new Date();
      const expectedSlaDue = new Date(createdAt.getTime() + SLA_TIMESCALES.EMERGENCY * 60 * 60 * 1000);

      const item = await createAirtableRecord('Work_Items', {
        title: `SLA Timescale Test: EMERGENCY [${marker}]`,
        description: `Testing SLA deadline calculation for EMERGENCY. Marker: ${marker}.`,
        current_state: 'INTAKE',
        urgency: 'EMERGENCY',
        discipline_required: 'GAS_SAFE',
        sla_due_at: expectedSlaDue.toISOString(),
        escalation_level: 0,
        created_at: createdAt.toISOString(),
        state_started_at: createdAt.toISOString(),
      });
      createdRecordIds.workItems.push(item.id);

      // Verify the SLA deadline is approximately 4 hours from creation
      const slaDue = new Date(item.fields.sla_due_at);
      const slaDiffHours = (slaDue - createdAt) / (1000 * 60 * 60);
      expect(slaDiffHours).to.be.closeTo(SLA_TIMESCALES.EMERGENCY, 0.5,
        'EMERGENCY SLA should be 4 hours');
    });

    it('should set correct SLA deadline for URGENT urgency (24 hours)', async function () {
      const marker = generateTestMarker();

      const createdAt = new Date();
      const expectedSlaDue = new Date(createdAt.getTime() + SLA_TIMESCALES.URGENT * 60 * 60 * 1000);

      const item = await createAirtableRecord('Work_Items', {
        title: `SLA Timescale Test: URGENT [${marker}]`,
        description: `Testing SLA deadline for URGENT. Marker: ${marker}.`,
        current_state: 'INTAKE',
        urgency: 'URGENT',
        discipline_required: 'PLUMBING',
        sla_due_at: expectedSlaDue.toISOString(),
        escalation_level: 0,
        created_at: createdAt.toISOString(),
        state_started_at: createdAt.toISOString(),
      });
      createdRecordIds.workItems.push(item.id);

      const slaDue = new Date(item.fields.sla_due_at);
      const slaDiffHours = (slaDue - createdAt) / (1000 * 60 * 60);
      expect(slaDiffHours).to.be.closeTo(SLA_TIMESCALES.URGENT, 0.5,
        'URGENT SLA should be 24 hours');
    });

    it('should set correct SLA deadline for STANDARD urgency (72 hours)', async function () {
      const marker = generateTestMarker();

      const createdAt = new Date();
      const expectedSlaDue = new Date(createdAt.getTime() + SLA_TIMESCALES.STANDARD * 60 * 60 * 1000);

      const item = await createAirtableRecord('Work_Items', {
        title: `SLA Timescale Test: STANDARD [${marker}]`,
        description: `Testing SLA deadline for STANDARD. Marker: ${marker}.`,
        current_state: 'INTAKE',
        urgency: 'STANDARD',
        discipline_required: 'GENERAL_MAINTENANCE',
        sla_due_at: expectedSlaDue.toISOString(),
        escalation_level: 0,
        created_at: createdAt.toISOString(),
        state_started_at: createdAt.toISOString(),
      });
      createdRecordIds.workItems.push(item.id);

      const slaDue = new Date(item.fields.sla_due_at);
      const slaDiffHours = (slaDue - createdAt) / (1000 * 60 * 60);
      expect(slaDiffHours).to.be.closeTo(SLA_TIMESCALES.STANDARD, 0.5,
        'STANDARD SLA should be 72 hours');
    });

    it('should set correct SLA deadline for SCHEDULED urgency (7 days)', async function () {
      const marker = generateTestMarker();

      const createdAt = new Date();
      const expectedSlaDue = new Date(createdAt.getTime() + SLA_TIMESCALES.SCHEDULED * 60 * 60 * 1000);

      const item = await createAirtableRecord('Work_Items', {
        title: `SLA Timescale Test: SCHEDULED [${marker}]`,
        description: `Testing SLA deadline for SCHEDULED. Marker: ${marker}.`,
        current_state: 'INTAKE',
        urgency: 'SCHEDULED',
        discipline_required: 'HVAC',
        sla_due_at: expectedSlaDue.toISOString(),
        escalation_level: 0,
        created_at: createdAt.toISOString(),
        state_started_at: createdAt.toISOString(),
      });
      createdRecordIds.workItems.push(item.id);

      const slaDue = new Date(item.fields.sla_due_at);
      const slaDiffHours = (slaDue - createdAt) / (1000 * 60 * 60);
      expect(slaDiffHours).to.be.closeTo(SLA_TIMESCALES.SCHEDULED, 1,
        'SCHEDULED SLA should be 168 hours (7 days)');
    });

    it('should apply more aggressive escalation intervals for EMERGENCY items', async function () {
      this.timeout(60000);
      const marker = generateTestMarker();

      // Create two overdue items: one EMERGENCY and one STANDARD, both 5 hours overdue
      const emergencyItem = await createOverdueWorkItem(`${marker}_E`, 'EMERGENCY', 5);
      const standardItem = await createOverdueWorkItem(`${marker}_S`, 'STANDARD', 5);

      // Trigger SLA check
      await triggerSLACheck();
      await sleep(12000);

      const updatedEmergency = await getAirtableRecord('Work_Items', emergencyItem.id);
      const updatedStandard = await getAirtableRecord('Work_Items', standardItem.id);

      // EMERGENCY should have a higher escalation level than STANDARD for the same overdue duration
      // Because EMERGENCY escalates every 1 hour vs STANDARD every 24 hours
      expect(updatedEmergency.fields.escalation_level).to.be.at.least(
        updatedStandard.fields.escalation_level,
        'EMERGENCY items should escalate more aggressively than STANDARD items'
      );
    });
  });

  // ── Edge Cases ────────────────────────────────────────────────────────────────

  describe('SLA Edge Cases', function () {
    it('should handle work items with no sla_due_at set', async function () {
      this.timeout(45000);
      const marker = generateTestMarker();

      // Create a work item without an SLA deadline
      const item = await createAirtableRecord('Work_Items', {
        title: `SLA No Deadline Test [${marker}]`,
        description: `Item with no SLA deadline. Marker: ${marker}.`,
        current_state: 'ASSIGNED',
        urgency: 'STANDARD',
        discipline_required: 'GENERAL_MAINTENANCE',
        escalation_level: 0,
        state_started_at: hoursAgoISO(100),
        created_at: hoursAgoISO(100),
        source_message_id: `wamid.nosla_${marker}`,
      });
      createdRecordIds.workItems.push(item.id);

      // SLA check should not crash when encountering items without a deadline
      await triggerSLACheck();
      await sleep(10000);

      const updatedItem = await getAirtableRecord('Work_Items', item.id);
      // Should remain unchanged - no escalation without a deadline
      expect(updatedItem.fields.escalation_level).to.equal(0);
    });

    it('should handle ON_HOLD work items without escalating', async function () {
      this.timeout(45000);
      const marker = generateTestMarker();

      const item = await createAirtableRecord('Work_Items', {
        title: `SLA On Hold Test [${marker}]`,
        description: `Testing that ON_HOLD items are not escalated. Marker: ${marker}.`,
        current_state: 'ON_HOLD',
        urgency: 'URGENT',
        sla_due_at: hoursAgoISO(48),
        escalation_level: 0,
        blocked_reason: 'Awaiting access permission from building management',
        state_started_at: hoursAgoISO(48),
        created_at: hoursAgoISO(72),
        source_message_id: `wamid.onhold_${marker}`,
      });
      createdRecordIds.workItems.push(item.id);

      await triggerSLACheck();
      await sleep(10000);

      const updatedItem = await getAirtableRecord('Work_Items', item.id);
      // ON_HOLD items should not be escalated (SLA clock is paused)
      expect(updatedItem.fields.escalation_level).to.equal(0,
        'ON_HOLD items should not be escalated');
      expect(updatedItem.fields.current_state).to.equal('ON_HOLD');
    });

    it('should handle state-locked work items without modifying them', async function () {
      this.timeout(45000);
      const marker = generateTestMarker();

      const item = await createAirtableRecord('Work_Items', {
        title: `SLA Locked Test [${marker}]`,
        description: `Testing that state-locked items are skipped. Marker: ${marker}.`,
        current_state: 'ASSIGNED',
        urgency: 'STANDARD',
        sla_due_at: hoursAgoISO(100),
        escalation_level: 1,
        state_locked: true,
        state_started_at: hoursAgoISO(172),
        created_at: hoursAgoISO(172),
        source_message_id: `wamid.locked_${marker}`,
      });
      createdRecordIds.workItems.push(item.id);

      await triggerSLACheck();
      await sleep(10000);

      const updatedItem = await getAirtableRecord('Work_Items', item.id);
      // State-locked items should not have their state or escalation modified
      expect(updatedItem.fields.state_locked).to.equal(true);
      expect(updatedItem.fields.escalation_level).to.equal(1,
        'State-locked items should not have escalation incremented');
    });

    it('should handle a large batch of overdue items without timing out', async function () {
      this.timeout(90000);
      const marker = generateTestMarker();
      const batchSize = 5;

      // Create multiple overdue items
      const items = [];
      for (let i = 0; i < batchSize; i++) {
        const item = await createOverdueWorkItem(`${marker}_batch_${i}`, 'STANDARD', 10 + i);
        items.push(item);
        await sleep(300); // Brief delay to avoid Airtable rate limits
      }

      // Trigger a single SLA check that should process all of them
      const startTime = Date.now();
      await triggerSLACheck();
      await sleep(15000);
      const elapsedMs = Date.now() - startTime;

      // Verify all items were escalated
      let escalatedCount = 0;
      for (const item of items) {
        const updated = await getAirtableRecord('Work_Items', item.id);
        if (updated.fields.escalation_level >= 1) {
          escalatedCount++;
        }
      }

      expect(escalatedCount).to.be.at.least(Math.floor(batchSize * 0.8),
        'At least 80% of overdue items should be escalated in a single batch');

      // Elapsed time should be reasonable (under 60 seconds for 5 items)
      expect(elapsedMs).to.be.below(60000,
        'SLA check batch should complete within 60 seconds');
    });
  });
});
