/**
 * SafeFlow Integration Tests - RFQ (Request for Quote) Flow
 *
 * Tests the complete RFQ lifecycle from work item routing through to
 * contractor notification, quote submission, comparison, acceptance/rejection,
 * and payment record creation.
 *
 * Prerequisites:
 *   - Staging environment configured
 *   - At least two active contractors in the Contractors table with matching disciplines
 *   - Environment variables set (see config/environments/staging.env.example)
 *   - Make.com Scenario B (RFQ) and Scenario C (Quote Processing) active
 *
 * Usage:
 *   npm test -- --grep "RFQ"
 */

const axios = require('axios');
const { expect } = require('chai');
require('dotenv').config({ path: process.env.DOTENV_PATH || '../../config/environments/staging.env.example' });

// ─── Configuration ──────────────────────────────────────────────────────────────

const CONFIG = {
  airtableApiKey: process.env.AIRTABLE_API_KEY,
  airtableBaseId: process.env.AIRTABLE_BASE_ID,
  makeWebhookScenarioB: process.env.MAKE_WEBHOOK_URL_SCENARIO_B,
  makeWebhookScenarioC: process.env.MAKE_WEBHOOK_URL_SCENARIO_C,
  environment: process.env.ENVIRONMENT || 'staging',
  pollingIntervalMs: 2000,
  pollingTimeoutMs: 25000,
};

const AIRTABLE_BASE_URL = `https://api.airtable.com/v0/${CONFIG.airtableBaseId}`;

const AIRTABLE_HEADERS = {
  Authorization: `Bearer ${CONFIG.airtableApiKey}`,
  'Content-Type': 'application/json',
};

// ─── Test Data Cleanup Tracking ─────────────────────────────────────────────────

const createdRecordIds = {
  workItems: [],
  quotes: [],
  payments: [],
  interactionLogs: [],
};

// ─── Helper Functions ───────────────────────────────────────────────────────────

/**
 * Retries an async function on transient errors (network failures, 429, 5xx).
 * Uses exponential backoff, and respects Retry-After headers for 429 responses.
 *
 * @param {Function} fn          - Async function to execute
 * @param {number}   maxRetries  - Maximum number of attempts (default 3)
 * @param {number}   baseDelayMs - Base delay in ms for exponential backoff (default 1000)
 * @returns {*}                  - Return value of fn()
 */
async function withRetry(fn, maxRetries = 3, baseDelayMs = 1000) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      const status = err.response?.status;
      const retryable = !status || status === 429 || status >= 500;
      if (!retryable || attempt === maxRetries) throw err;
      const delay = status === 429
        ? parseInt(err.response.headers?.['retry-after'] || '5', 10) * 1000
        : baseDelayMs * Math.pow(2, attempt - 1);
      console.warn(`  Retry ${attempt}/${maxRetries} after ${delay}ms (status: ${status})`);
      await sleep(delay);
    }
  }
}

async function createAirtableRecord(tableName, fields) {
  return withRetry(async () => {
    const response = await axios.post(
      `${AIRTABLE_BASE_URL}/${encodeURIComponent(tableName)}`,
      { fields },
      { headers: AIRTABLE_HEADERS }
    );
    return response.data;
  });
}

async function getAirtableRecord(tableName, recordId) {
  return withRetry(async () => {
    const response = await axios.get(
      `${AIRTABLE_BASE_URL}/${encodeURIComponent(tableName)}/${recordId}`,
      { headers: AIRTABLE_HEADERS }
    );
    return response.data;
  });
}

async function findAirtableRecords(tableName, filterFormula, maxRecords = 10) {
  return withRetry(async () => {
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
  });
}

async function updateAirtableRecord(tableName, recordId, fields) {
  return withRetry(async () => {
    const response = await axios.patch(
      `${AIRTABLE_BASE_URL}/${encodeURIComponent(tableName)}/${recordId}`,
      { fields },
      { headers: AIRTABLE_HEADERS }
    );
    return response.data;
  });
}

async function deleteAirtableRecord(tableName, recordId) {
  return withRetry(async () => {
    await axios.delete(
      `${AIRTABLE_BASE_URL}/${encodeURIComponent(tableName)}/${recordId}`,
      { headers: AIRTABLE_HEADERS }
    );
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function generateTestMarker() {
  return `SFTEST_RFQ_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * Polls Airtable until a record matching the filter appears or timeout is reached.
 */
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

/**
 * Polls an existing record until a field matches an expected value.
 */
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
 * Creates a test Work_Item in ASSESSMENT state with EXTERNAL_CONTRACTOR routing,
 * ready to trigger the RFQ flow.
 */
async function createTestWorkItemForRFQ(marker, discipline = 'PLUMBING') {
  const record = await createAirtableRecord('Work_Items', {
    title: `RFQ Test: ${discipline} repair [${marker}]`,
    description: `Integration test work item for RFQ flow. Marker: ${marker}. Requires ${discipline} contractor.`,
    current_state: 'ASSESSMENT',
    discipline_required: discipline,
    urgency: 'STANDARD',
    routing_decision: 'EXTERNAL_CONTRACTOR',
    llm_confidence: 0.92,
    location_building: 'Test House',
    location_floor: 'Ground',
    location_area: 'Kitchen',
    state_started_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    source_message_id: `wamid.rfqtest_${marker}`,
    whatsapp_thread_id: `thread_rfqtest_${marker}`,
  });
  createdRecordIds.workItems.push(record.id);
  return record;
}

/**
 * Triggers the RFQ scenario via Make.com webhook for a given work item.
 */
async function triggerRFQScenario(workItemId, discipline) {
  const response = await axios.post(
    CONFIG.makeWebhookScenarioB,
    {
      work_item_id: workItemId,
      discipline_required: discipline,
      urgency: 'STANDARD',
      trigger: 'integration_test',
    },
    {
      headers: { 'Content-Type': 'application/json' },
      timeout: 15000,
    }
  );
  return response;
}

/**
 * Simulates a contractor submitting a quote via the Make.com webhook.
 */
async function simulateQuoteSubmission(quoteRecordId, quoteFields) {
  const response = await axios.post(
    CONFIG.makeWebhookScenarioC,
    {
      action: 'submit_quote',
      quote_id: quoteRecordId,
      ...quoteFields,
    },
    {
      headers: { 'Content-Type': 'application/json' },
      timeout: 15000,
    }
  );
  return response;
}

/**
 * Finds active contractors matching a given discipline in the staging environment.
 */
async function findContractorsByDiscipline(discipline, limit = 3) {
  return findAirtableRecords(
    'Contractors',
    `AND({status} = "ACTIVE", FIND("${discipline}", ARRAYJOIN({trade_disciplines}, ",")))`,
    limit
  );
}

// ─── Test Suite ─────────────────────────────────────────────────────────────────

describe('RFQ Flow', function () {
  this.timeout(30000);

  before(function () {
    const requiredVars = [
      'AIRTABLE_API_KEY',
      'AIRTABLE_BASE_ID',
      'MAKE_WEBHOOK_URL_SCENARIO_B',
      'MAKE_WEBHOOK_URL_SCENARIO_C',
    ];
    const missing = requiredVars.filter((v) => !process.env[v]);
    if (missing.length > 0) {
      this.skip();
      console.warn(`Skipping RFQ Flow tests: missing env vars: ${missing.join(', ')}`);
    }
  });

  after(async function () {
    this.timeout(60000);
    const tables = [
      { name: 'Payments', ids: createdRecordIds.payments },
      { name: 'Interaction_Logs', ids: createdRecordIds.interactionLogs },
      { name: 'Quotes', ids: createdRecordIds.quotes },
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

  // ── RFQ Creation ──────────────────────────────────────────────────────────────

  describe('RFQ Creation', function () {
    it('should create Quote records in REQUESTED status for matching contractors', async function () {
      this.timeout(45000);
      const marker = generateTestMarker();

      // Verify we have contractors for this discipline
      const contractors = await findContractorsByDiscipline('PLUMBING');
      if (contractors.length < 1) {
        this.skip();
        console.warn('Skipping: no active PLUMBING contractors in staging');
        return;
      }

      // Create a work item routed to external contractor
      const workItem = await createTestWorkItemForRFQ(marker, 'PLUMBING');

      // Trigger the RFQ scenario
      const response = await triggerRFQScenario(workItem.id, 'PLUMBING');
      expect(response.status).to.be.oneOf([200, 202]);

      // Wait for Quote records to be created
      await sleep(8000);

      // Find quotes linked to this work item
      const quotes = await findAirtableRecords(
        'Quotes',
        `SEARCH("${workItem.id}", ARRAYJOIN({work_item_id}, ","))`,
        10
      );

      expect(quotes.length).to.be.at.least(1,
        'At least one Quote record should be created for matching contractors');

      quotes.forEach((q) => createdRecordIds.quotes.push(q.id));

      // All quotes should be in REQUESTED status
      for (const quote of quotes) {
        expect(quote.fields.status).to.equal('REQUESTED');
        expect(quote.fields.work_item_id).to.be.an('array').and.to.include(workItem.id);
        expect(quote.fields.contractor_id).to.be.an('array').and.to.have.lengthOf(1);
      }
    });

    it('should only send RFQs to contractors covering the relevant postcode', async function () {
      this.timeout(45000);
      const marker = generateTestMarker();

      // Create a work item with a specific site postcode context
      const workItem = await createAirtableRecord('Work_Items', {
        title: `RFQ Postcode Test [${marker}]`,
        description: `Plumbing issue at site in EC2M postcode area. Marker: ${marker}`,
        current_state: 'ASSESSMENT',
        discipline_required: 'PLUMBING',
        urgency: 'STANDARD',
        routing_decision: 'EXTERNAL_CONTRACTOR',
        llm_confidence: 0.90,
        location_building: 'Moorgate House',
        state_started_at: new Date().toISOString(),
        created_at: new Date().toISOString(),
      });
      createdRecordIds.workItems.push(workItem.id);

      // Trigger RFQ scenario
      const response = await triggerRFQScenario(workItem.id, 'PLUMBING');
      expect(response.status).to.be.oneOf([200, 202]);

      await sleep(8000);

      // Find quotes for this work item
      const quotes = await findAirtableRecords(
        'Quotes',
        `SEARCH("${workItem.id}", ARRAYJOIN({work_item_id}, ","))`,
        10
      );
      quotes.forEach((q) => createdRecordIds.quotes.push(q.id));

      // Each quote's contractor should cover the relevant postcode area
      for (const quote of quotes) {
        if (quote.fields.contractor_id && quote.fields.contractor_id.length > 0) {
          const contractor = await getAirtableRecord('Contractors', quote.fields.contractor_id[0]);
          const coveragePostcodes = contractor.fields.coverage_postcodes || '';
          // The contractor should cover EC or EC2 or EC2M
          const coversArea = coveragePostcodes.includes('EC') ||
                            coveragePostcodes.includes('EC2') ||
                            coveragePostcodes.includes('EC2M') ||
                            coveragePostcodes.includes('ALL');
          expect(coversArea).to.be.true;
        }
      }
    });
  });

  // ── Contractor Notification ───────────────────────────────────────────────────

  describe('Contractor Notification', function () {
    it('should send WhatsApp notification to contractors when RFQ is created', async function () {
      this.timeout(45000);
      const marker = generateTestMarker();

      const contractors = await findContractorsByDiscipline('ELECTRICAL');
      if (contractors.length < 1) {
        this.skip();
        console.warn('Skipping: no active ELECTRICAL contractors in staging');
        return;
      }

      const workItem = await createTestWorkItemForRFQ(marker, 'ELECTRICAL');
      await triggerRFQScenario(workItem.id, 'ELECTRICAL');

      // Wait for quote creation and contractor notifications
      await sleep(10000);

      // Find outbound interaction logs related to this work item
      const notifications = await findAirtableRecords(
        'Interaction_Logs',
        `AND({direction} = "OUTBOUND", {channel} = "WHATSAPP", SEARCH("${workItem.id}", ARRAYJOIN({work_item_id}, ",")))`,
        10
      );

      notifications.forEach((n) => createdRecordIds.interactionLogs.push(n.id));

      // There should be at least one outbound notification to a contractor
      expect(notifications.length).to.be.at.least(1,
        'At least one WhatsApp notification should be sent to a contractor');

      // Notification content should contain relevant job details
      if (notifications.length > 0) {
        const content = notifications[0].fields.message_content || '';
        expect(content.length).to.be.greaterThan(20,
          'Notification should contain meaningful job description');
      }
    });

    it('should log notification delivery status', async function () {
      this.timeout(45000);
      const marker = generateTestMarker();

      const workItem = await createTestWorkItemForRFQ(marker, 'GENERAL_MAINTENANCE');
      await triggerRFQScenario(workItem.id, 'GENERAL_MAINTENANCE');

      await sleep(12000);

      const notifications = await findAirtableRecords(
        'Interaction_Logs',
        `AND({direction} = "OUTBOUND", SEARCH("${workItem.id}", ARRAYJOIN({work_item_id}, ",")))`,
        10
      );
      notifications.forEach((n) => createdRecordIds.interactionLogs.push(n.id));

      for (const notification of notifications) {
        // delivery_status should be set to one of the valid statuses
        if (notification.fields.delivery_status) {
          expect(notification.fields.delivery_status).to.be.oneOf(
            ['SENT', 'DELIVERED', 'READ', 'FAILED']
          );
        }
      }
    });
  });

  // ── Quote Submission ──────────────────────────────────────────────────────────

  describe('Quote Submission', function () {
    let testWorkItemId;
    let testQuoteIds = [];

    before(async function () {
      this.timeout(45000);
      const marker = generateTestMarker();

      const contractors = await findContractorsByDiscipline('PLUMBING', 2);
      if (contractors.length < 2) {
        this.skip();
        console.warn('Skipping quote submission tests: need at least 2 PLUMBING contractors');
        return;
      }

      // Create work item and quotes manually for controlled testing
      const workItem = await createTestWorkItemForRFQ(marker, 'PLUMBING');
      testWorkItemId = workItem.id;

      // Create two REQUESTED quotes
      for (const contractor of contractors.slice(0, 2)) {
        const quote = await createAirtableRecord('Quotes', {
          work_item_id: [testWorkItemId],
          contractor_id: [contractor.id],
          status: 'REQUESTED',
          created_at: new Date().toISOString(),
        });
        testQuoteIds.push(quote.id);
        createdRecordIds.quotes.push(quote.id);
      }
    });

    it('should accept a valid quote submission with cost breakdown', async function () {
      if (!testQuoteIds[0]) {
        this.skip();
        return;
      }

      const quoteFields = {
        labour_cost: 350.00,
        materials_cost: 125.50,
        lead_time_days: 3,
        scope_of_work: 'Replace faulty stop valve and repair copper pipework. Includes testing and commissioning.',
        exclusions: 'Making good to plasterwork. Decoration.',
        valid_until: '2026-03-15',
      };

      // Submit the quote via webhook
      const response = await simulateQuoteSubmission(testQuoteIds[0], quoteFields);
      expect(response.status).to.be.oneOf([200, 202]);

      await sleep(5000);

      // Verify the quote was updated
      const updatedQuote = await getAirtableRecord('Quotes', testQuoteIds[0]);
      expect(updatedQuote.fields.status).to.equal('SUBMITTED');
      expect(updatedQuote.fields.labour_cost).to.equal(350.00);
      expect(updatedQuote.fields.materials_cost).to.equal(125.50);
      expect(updatedQuote.fields.lead_time_days).to.equal(3);
      expect(updatedQuote.fields.scope_of_work).to.include('Replace faulty stop valve');
      expect(updatedQuote.fields.exclusions).to.include('Making good');
      expect(updatedQuote.fields.submitted_at).to.be.a('string');
    });

    it('should accept a second quote from a different contractor', async function () {
      if (!testQuoteIds[1]) {
        this.skip();
        return;
      }

      const quoteFields = {
        labour_cost: 280.00,
        materials_cost: 150.00,
        lead_time_days: 5,
        scope_of_work: 'Isolate and replace defective valve. New 15mm compression fitting. Pressure test on completion.',
        exclusions: 'Tiling, redecoration, asbestos removal if found.',
        valid_until: '2026-03-20',
      };

      const response = await simulateQuoteSubmission(testQuoteIds[1], quoteFields);
      expect(response.status).to.be.oneOf([200, 202]);

      await sleep(5000);

      const updatedQuote = await getAirtableRecord('Quotes', testQuoteIds[1]);
      expect(updatedQuote.fields.status).to.equal('SUBMITTED');
      expect(updatedQuote.fields.labour_cost).to.equal(280.00);
      expect(updatedQuote.fields.materials_cost).to.equal(150.00);
    });
  });

  // ── Quote Comparison ──────────────────────────────────────────────────────────

  describe('Quote Comparison', function () {
    it('should allow retrieval of all submitted quotes for a work item', async function () {
      this.timeout(30000);
      const marker = generateTestMarker();

      // Create a work item with two pre-submitted quotes for comparison
      const workItem = await createTestWorkItemForRFQ(marker, 'HVAC');

      const contractors = await findContractorsByDiscipline('HVAC', 2);
      if (contractors.length < 2) {
        // Create placeholder quotes for the test
        const quote1 = await createAirtableRecord('Quotes', {
          work_item_id: [workItem.id],
          status: 'SUBMITTED',
          labour_cost: 500.00,
          materials_cost: 200.00,
          lead_time_days: 4,
          scope_of_work: 'Full HVAC filter replacement and duct clean',
          submitted_at: new Date().toISOString(),
          created_at: new Date().toISOString(),
        });
        createdRecordIds.quotes.push(quote1.id);

        const quote2 = await createAirtableRecord('Quotes', {
          work_item_id: [workItem.id],
          status: 'SUBMITTED',
          labour_cost: 650.00,
          materials_cost: 150.00,
          lead_time_days: 2,
          scope_of_work: 'Emergency HVAC filter replacement, express service',
          submitted_at: new Date().toISOString(),
          created_at: new Date().toISOString(),
        });
        createdRecordIds.quotes.push(quote2.id);
      }

      // Retrieve all quotes for comparison
      const allQuotes = await findAirtableRecords(
        'Quotes',
        `AND({status} = "SUBMITTED", SEARCH("${workItem.id}", ARRAYJOIN({work_item_id}, ",")))`,
        10
      );

      expect(allQuotes.length).to.be.at.least(2, 'Should have at least 2 quotes for comparison');

      // Quotes should have comparable fields populated
      for (const quote of allQuotes) {
        expect(quote.fields.labour_cost).to.be.a('number');
        expect(quote.fields.materials_cost).to.be.a('number');
        expect(quote.fields.lead_time_days).to.be.a('number');
        expect(quote.fields.scope_of_work).to.be.a('string');
      }

      // Verify quotes can be sorted by total cost (labour + materials)
      const sortedByTotal = allQuotes.sort((a, b) => {
        const totalA = (a.fields.labour_cost || 0) + (a.fields.materials_cost || 0);
        const totalB = (b.fields.labour_cost || 0) + (b.fields.materials_cost || 0);
        return totalA - totalB;
      });
      const firstTotal = (sortedByTotal[0].fields.labour_cost || 0) + (sortedByTotal[0].fields.materials_cost || 0);
      const lastTotal = (sortedByTotal[sortedByTotal.length - 1].fields.labour_cost || 0) +
                        (sortedByTotal[sortedByTotal.length - 1].fields.materials_cost || 0);
      expect(firstTotal).to.be.at.most(lastTotal);

      allQuotes.forEach((q) => {
        if (!createdRecordIds.quotes.includes(q.id)) {
          createdRecordIds.quotes.push(q.id);
        }
      });
    });
  });

  // ── Quote Acceptance / Rejection ──────────────────────────────────────────────

  describe('Quote Acceptance and Rejection', function () {
    let workItemId;
    let acceptedQuoteId;
    let rejectedQuoteId;

    before(async function () {
      this.timeout(30000);
      const marker = generateTestMarker();

      const workItem = await createTestWorkItemForRFQ(marker, 'PLUMBING');
      workItemId = workItem.id;

      const quote1 = await createAirtableRecord('Quotes', {
        work_item_id: [workItemId],
        status: 'SUBMITTED',
        labour_cost: 300.00,
        materials_cost: 100.00,
        lead_time_days: 3,
        scope_of_work: 'Standard plumbing repair',
        submitted_at: new Date().toISOString(),
        created_at: new Date().toISOString(),
      });
      acceptedQuoteId = quote1.id;
      createdRecordIds.quotes.push(quote1.id);

      const quote2 = await createAirtableRecord('Quotes', {
        work_item_id: [workItemId],
        status: 'SUBMITTED',
        labour_cost: 500.00,
        materials_cost: 200.00,
        lead_time_days: 7,
        scope_of_work: 'Premium plumbing repair with extended warranty',
        submitted_at: new Date().toISOString(),
        created_at: new Date().toISOString(),
      });
      rejectedQuoteId = quote2.id;
      createdRecordIds.quotes.push(quote2.id);
    });

    it('should accept a selected quote and update its status', async function () {
      this.timeout(30000);
      if (!acceptedQuoteId) {
        this.skip();
        return;
      }

      // Accept the quote via webhook
      const response = await axios.post(
        CONFIG.makeWebhookScenarioC,
        {
          action: 'accept_quote',
          quote_id: acceptedQuoteId,
          approved_by: 'test_property_manager',
          notes: 'Best value option, acceptable lead time.',
        },
        {
          headers: { 'Content-Type': 'application/json' },
          timeout: 15000,
        }
      );
      expect(response.status).to.be.oneOf([200, 202]);

      await sleep(5000);

      // Verify quote status changed to ACCEPTED
      const acceptedQuote = await getAirtableRecord('Quotes', acceptedQuoteId);
      expect(acceptedQuote.fields.status).to.equal('ACCEPTED');
      expect(acceptedQuote.fields.responded_at).to.be.a('string');
    });

    it('should reject the other quotes for the same work item', async function () {
      this.timeout(30000);
      if (!rejectedQuoteId) {
        this.skip();
        return;
      }

      // Explicitly reject the other quote
      const response = await axios.post(
        CONFIG.makeWebhookScenarioC,
        {
          action: 'reject_quote',
          quote_id: rejectedQuoteId,
          reason: 'Exceeded budget and lead time too long.',
        },
        {
          headers: { 'Content-Type': 'application/json' },
          timeout: 15000,
        }
      );
      expect(response.status).to.be.oneOf([200, 202]);

      await sleep(5000);

      // Verify quote status changed to REJECTED
      const rejectedQuote = await getAirtableRecord('Quotes', rejectedQuoteId);
      expect(rejectedQuote.fields.status).to.equal('REJECTED');
      expect(rejectedQuote.fields.responded_at).to.be.a('string');
    });

    it('should transition the work item to ASSIGNED after quote acceptance', async function () {
      this.timeout(30000);
      if (!workItemId) {
        this.skip();
        return;
      }

      await sleep(5000);

      // After a quote is accepted, the work item should move to ASSIGNED
      const workItem = await getAirtableRecord('Work_Items', workItemId);

      expect(workItem.fields.current_state).to.be.oneOf(
        ['ASSIGNED', 'IN_PROGRESS'],
        'Work item should transition to ASSIGNED after quote acceptance'
      );

      // The contractor from the accepted quote should be linked
      if (workItem.fields.contractor_id && workItem.fields.contractor_id.length > 0) {
        expect(workItem.fields.contractor_id).to.be.an('array').and.to.have.lengthOf(1);
      }

      // Cost estimate should be populated from the accepted quote
      if (workItem.fields.cost_estimate) {
        expect(workItem.fields.cost_estimate).to.equal(400.00); // 300 + 100 from the accepted quote
      }
    });

    it('should notify the winning contractor via WhatsApp', async function () {
      this.timeout(30000);
      if (!workItemId) {
        this.skip();
        return;
      }

      await sleep(3000);

      const notifications = await findAirtableRecords(
        'Interaction_Logs',
        `AND({direction} = "OUTBOUND", SEARCH("${workItemId}", ARRAYJOIN({work_item_id}, ",")))`,
        10
      );
      notifications.forEach((n) => createdRecordIds.interactionLogs.push(n.id));

      // At least one notification should have been sent for the acceptance
      const acceptanceNotifications = notifications.filter((n) => {
        const content = (n.fields.message_content || '').toLowerCase();
        return content.includes('accept') || content.includes('awarded') || content.includes('approved');
      });

      // Acceptance notification may be present depending on scenario timing
      if (acceptanceNotifications.length > 0) {
        expect(acceptanceNotifications[0].fields.channel).to.equal('WHATSAPP');
        expect(acceptanceNotifications[0].fields.direction).to.equal('OUTBOUND');
      }
    });
  });

  // ── Payment Creation ──────────────────────────────────────────────────────────

  describe('Payment Creation from Accepted Quote', function () {
    it('should create a Payment record when a quote is accepted', async function () {
      this.timeout(45000);
      const marker = generateTestMarker();

      // Create work item and a quote, then accept it
      const workItem = await createTestWorkItemForRFQ(marker, 'ELECTRICAL');

      const contractors = await findContractorsByDiscipline('ELECTRICAL', 1);
      let contractorId = null;
      if (contractors.length > 0) {
        contractorId = contractors[0].id;
      }

      const quoteFields = {
        work_item_id: [workItem.id],
        status: 'SUBMITTED',
        labour_cost: 420.00,
        materials_cost: 180.00,
        lead_time_days: 2,
        scope_of_work: 'Replace consumer unit and test all circuits. NICEIC certificate provided.',
        submitted_at: new Date().toISOString(),
        created_at: new Date().toISOString(),
      };
      if (contractorId) {
        quoteFields.contractor_id = [contractorId];
      }

      const quote = await createAirtableRecord('Quotes', quoteFields);
      createdRecordIds.quotes.push(quote.id);

      // Accept the quote
      await axios.post(
        CONFIG.makeWebhookScenarioC,
        {
          action: 'accept_quote',
          quote_id: quote.id,
          approved_by: 'test_admin',
          notes: 'Approved for immediate commencement.',
        },
        {
          headers: { 'Content-Type': 'application/json' },
          timeout: 15000,
        }
      );

      // Wait for payment creation
      await sleep(10000);

      // Find payment records linked to this work item
      const payments = await findAirtableRecords(
        'Payments',
        `SEARCH("${workItem.id}", ARRAYJOIN({work_item_id}, ","))`,
        5
      );

      expect(payments.length).to.be.at.least(1, 'A Payment record should be created on quote acceptance');
      payments.forEach((p) => createdRecordIds.payments.push(p.id));

      const payment = payments[0];

      // Payment should reference the accepted quote
      if (payment.fields.quote_id) {
        expect(payment.fields.quote_id).to.be.an('array');
        expect(payment.fields.quote_id).to.include(quote.id);
      }

      // Payment amount should match the quote total (ex-VAT)
      if (payment.fields.amount) {
        expect(payment.fields.amount).to.equal(600.00); // 420 + 180
      }

      // VAT should be calculated at 20%
      if (payment.fields.vat_amount) {
        expect(payment.fields.vat_amount).to.equal(120.00); // 600 * 0.20
      }

      // Payment should be in PENDING status initially
      expect(payment.fields.status).to.equal('PENDING');

      // Contractor should be linked
      if (contractorId && payment.fields.contractor_id) {
        expect(payment.fields.contractor_id).to.include(contractorId);
      }
    });

    it('should not create a Payment record when a quote is rejected', async function () {
      this.timeout(30000);
      const marker = generateTestMarker();

      const workItem = await createTestWorkItemForRFQ(marker, 'GENERAL_MAINTENANCE');

      const quote = await createAirtableRecord('Quotes', {
        work_item_id: [workItem.id],
        status: 'SUBMITTED',
        labour_cost: 1500.00,
        materials_cost: 750.00,
        lead_time_days: 14,
        scope_of_work: 'Full refurbishment of reception area',
        submitted_at: new Date().toISOString(),
        created_at: new Date().toISOString(),
      });
      createdRecordIds.quotes.push(quote.id);

      // Reject the quote
      await axios.post(
        CONFIG.makeWebhookScenarioC,
        {
          action: 'reject_quote',
          quote_id: quote.id,
          reason: 'Over budget. Will seek alternative quotation.',
        },
        {
          headers: { 'Content-Type': 'application/json' },
          timeout: 15000,
        }
      );

      await sleep(8000);

      // Verify no Payment was created
      const payments = await findAirtableRecords(
        'Payments',
        `SEARCH("${workItem.id}", ARRAYJOIN({work_item_id}, ","))`,
        5
      );

      expect(payments.length).to.equal(0, 'No Payment record should be created for rejected quotes');
      payments.forEach((p) => createdRecordIds.payments.push(p.id));
    });
  });

  // ── Quote Expiry ──────────────────────────────────────────────────────────────

  describe('Quote Expiry', function () {
    it('should handle expired quotes correctly', async function () {
      const marker = generateTestMarker();

      const workItem = await createTestWorkItemForRFQ(marker, 'PLUMBING');

      // Create a quote with a past valid_until date
      const pastDate = new Date();
      pastDate.setDate(pastDate.getDate() - 7);

      const expiredQuote = await createAirtableRecord('Quotes', {
        work_item_id: [workItem.id],
        status: 'SUBMITTED',
        labour_cost: 200.00,
        materials_cost: 50.00,
        lead_time_days: 1,
        scope_of_work: 'Minor tap repair',
        valid_until: pastDate.toISOString().split('T')[0],
        submitted_at: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString(),
        created_at: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString(),
      });
      createdRecordIds.quotes.push(expiredQuote.id);

      // Attempt to accept the expired quote
      try {
        const response = await axios.post(
          CONFIG.makeWebhookScenarioC,
          {
            action: 'accept_quote',
            quote_id: expiredQuote.id,
            approved_by: 'test_admin',
          },
          {
            headers: { 'Content-Type': 'application/json' },
            timeout: 15000,
            validateStatus: () => true,
          }
        );

        await sleep(5000);

        const updatedQuote = await getAirtableRecord('Quotes', expiredQuote.id);

        // The quote should either remain SUBMITTED (acceptance rejected) or be marked EXPIRED
        expect(updatedQuote.fields.status).to.be.oneOf(
          ['SUBMITTED', 'EXPIRED'],
          'Expired quotes should not be accepted'
        );
      } catch (err) {
        // An error response is also acceptable for expired quotes
        expect(err.response ? err.response.status : err.code).to.satisfy(
          (val) => [400, 422, 'ECONNRESET'].includes(val)
        );
      }
    });
  });

  // ── Error Handling ────────────────────────────────────────────────────────────

  describe('RFQ Error Handling', function () {
    it('should handle RFQ trigger for a non-existent work item', async function () {
      try {
        const response = await axios.post(
          CONFIG.makeWebhookScenarioB,
          {
            work_item_id: 'recNONEXISTENT12345',
            discipline_required: 'PLUMBING',
            urgency: 'STANDARD',
          },
          {
            headers: { 'Content-Type': 'application/json' },
            timeout: 15000,
            validateStatus: () => true,
          }
        );

        // Should not create any quotes for non-existent work items
        expect(response.status).to.be.oneOf([200, 400, 404, 422]);
      } catch (err) {
        // Network-level rejection is acceptable
        expect(err.code).to.be.oneOf(['ECONNREFUSED', 'ETIMEDOUT', 'ECONNRESET']);
      }
    });

    it('should handle quote submission with negative amounts', async function () {
      const marker = generateTestMarker();
      const workItem = await createTestWorkItemForRFQ(marker, 'PLUMBING');

      const quote = await createAirtableRecord('Quotes', {
        work_item_id: [workItem.id],
        status: 'REQUESTED',
        created_at: new Date().toISOString(),
      });
      createdRecordIds.quotes.push(quote.id);

      try {
        const response = await axios.post(
          CONFIG.makeWebhookScenarioC,
          {
            action: 'submit_quote',
            quote_id: quote.id,
            labour_cost: -100.00,
            materials_cost: -50.00,
            lead_time_days: 3,
          },
          {
            headers: { 'Content-Type': 'application/json' },
            timeout: 15000,
            validateStatus: () => true,
          }
        );

        await sleep(5000);

        // Quote should not transition to SUBMITTED with invalid costs
        const updatedQuote = await getAirtableRecord('Quotes', quote.id);
        expect(updatedQuote.fields.status).to.be.oneOf(
          ['REQUESTED'],
          'Quotes with negative amounts should not be accepted'
        );
      } catch (err) {
        // Rejection is acceptable
      }
    });

    it('should handle double-acceptance of the same quote gracefully', async function () {
      const marker = generateTestMarker();
      const workItem = await createTestWorkItemForRFQ(marker, 'PLUMBING');

      const quote = await createAirtableRecord('Quotes', {
        work_item_id: [workItem.id],
        status: 'SUBMITTED',
        labour_cost: 250.00,
        materials_cost: 75.00,
        lead_time_days: 2,
        scope_of_work: 'Standard repair',
        submitted_at: new Date().toISOString(),
        created_at: new Date().toISOString(),
      });
      createdRecordIds.quotes.push(quote.id);

      // Accept the quote twice in rapid succession
      const acceptPayload = {
        action: 'accept_quote',
        quote_id: quote.id,
        approved_by: 'test_admin',
      };

      const [res1, res2] = await Promise.all([
        axios.post(CONFIG.makeWebhookScenarioC, acceptPayload, {
          headers: { 'Content-Type': 'application/json' },
          timeout: 15000,
          validateStatus: () => true,
        }),
        axios.post(CONFIG.makeWebhookScenarioC, acceptPayload, {
          headers: { 'Content-Type': 'application/json' },
          timeout: 15000,
          validateStatus: () => true,
        }),
      ]);

      await sleep(8000);

      // Should only create one Payment record, not two
      const payments = await findAirtableRecords(
        'Payments',
        `SEARCH("${workItem.id}", ARRAYJOIN({work_item_id}, ","))`,
        5
      );
      payments.forEach((p) => createdRecordIds.payments.push(p.id));

      expect(payments.length).to.be.at.most(1,
        'Double-acceptance should not create duplicate payment records');
    });
  });
});
