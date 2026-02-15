/**
 * SafeFlow Integration Tests - Intake Flow
 *
 * Tests the complete lifecycle of a facilities management request
 * from WhatsApp message receipt through to work item creation and assignment.
 *
 * Prerequisites:
 *   - Staging environment configured
 *   - Environment variables set (see config/environments/staging.env.example)
 *   - Make.com scenarios active in staging
 *
 * Usage:
 *   npm test
 *   npm test -- --grep "intake"
 */

const axios = require('axios');
const { expect } = require('chai');
require('dotenv').config({ path: process.env.DOTENV_PATH || '../../config/environments/staging.env.example' });

// ─── Configuration ──────────────────────────────────────────────────────────────

const CONFIG = {
  airtableApiKey: process.env.AIRTABLE_API_KEY,
  airtableBaseId: process.env.AIRTABLE_BASE_ID,
  makeWebhookUrl: process.env.MAKE_WEBHOOK_URL_SCENARIO_A,
  whatsappPhoneNumberId: process.env.WHATSAPP_PHONE_NUMBER_ID,
  environment: process.env.ENVIRONMENT || 'staging',
  pollingIntervalMs: 2000,
  pollingTimeoutMs: 25000,
};

const AIRTABLE_BASE_URL = `https://api.airtable.com/v0/${CONFIG.airtableBaseId}`;

const AIRTABLE_HEADERS = {
  Authorization: `Bearer ${CONFIG.airtableApiKey}`,
  'Content-Type': 'application/json',
};

// ─── Test Data: UK-Specific Fixtures ────────────────────────────────────────────

const TEST_PHONE_KNOWN = '+447700900001';
const TEST_PHONE_UNKNOWN = '+447700900099';

const TEST_MESSAGES = {
  clearRequest: {
    text: 'Hi, the kitchen tap in unit 4B at Meridian House is leaking badly. Water is dripping onto the floor. Can someone come and fix it please?',
    expectedDiscipline: 'PLUMBING',
    expectedUrgency: 'STANDARD',
  },
  emergency: {
    text: 'URGENT - there is a strong smell of gas in the ground floor lobby of Whitfield Tower, SE1 7PQ. We have evacuated the building. Please send someone immediately.',
    expectedDiscipline: 'GAS_SAFE',
    expectedUrgency: 'EMERGENCY',
  },
  vagueMessage: {
    text: 'Something is wrong in the office. Can you help?',
    expectedState: 'CLARIFICATION',
  },
  imageCaption: {
    text: 'Damp patch on the ceiling in the third floor corridor, looks like it is getting worse',
    mediaUrl: 'https://staging-media.safeflow.io/test/damp-ceiling-sample.jpg',
    mediaType: 'image',
    expectedDiscipline: 'GENERAL_MAINTENANCE',
  },
  duplicateMessage: {
    text: 'Broken window in reception at Castlegate Business Park, LS2 8DJ. Glass is cracked and letting in cold air.',
  },
};

// ─── Test Data Cleanup Tracking ─────────────────────────────────────────────────

const createdRecordIds = {
  workItems: [],
  people: [],
  interactionLogs: [],
};

// ─── Helper Functions ───────────────────────────────────────────────────────────

/**
 * Creates or retrieves an Airtable record.
 * @param {string} tableName - Airtable table name
 * @param {object} fields    - Record fields
 * @returns {object}         - Created record { id, fields }
 */
async function createAirtableRecord(tableName, fields) {
  const response = await axios.post(
    `${AIRTABLE_BASE_URL}/${encodeURIComponent(tableName)}`,
    { fields },
    { headers: AIRTABLE_HEADERS }
  );
  return response.data;
}

/**
 * Retrieves an Airtable record by ID.
 * @param {string} tableName - Airtable table name
 * @param {string} recordId  - Record ID (e.g. recXXXXXXXXXXXXXX)
 * @returns {object}         - Record { id, fields }
 */
async function getAirtableRecord(tableName, recordId) {
  const response = await axios.get(
    `${AIRTABLE_BASE_URL}/${encodeURIComponent(tableName)}/${recordId}`,
    { headers: AIRTABLE_HEADERS }
  );
  return response.data;
}

/**
 * Searches Airtable for records matching a filter formula.
 * @param {string} tableName     - Airtable table name
 * @param {string} filterFormula - Airtable filter formula
 * @param {number} maxRecords    - Maximum records to return (default 10)
 * @returns {Array}              - Array of matching records
 */
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

/**
 * Deletes an Airtable record by ID. Used for test cleanup.
 * @param {string} tableName - Airtable table name
 * @param {string} recordId  - Record ID
 */
async function deleteAirtableRecord(tableName, recordId) {
  await axios.delete(
    `${AIRTABLE_BASE_URL}/${encodeURIComponent(tableName)}/${recordId}`,
    { headers: AIRTABLE_HEADERS }
  );
}

/**
 * Updates fields on an Airtable record.
 * @param {string} tableName - Airtable table name
 * @param {string} recordId  - Record ID
 * @param {object} fields    - Fields to update
 * @returns {object}         - Updated record
 */
async function updateAirtableRecord(tableName, recordId, fields) {
  const response = await axios.patch(
    `${AIRTABLE_BASE_URL}/${encodeURIComponent(tableName)}/${recordId}`,
    { fields },
    { headers: AIRTABLE_HEADERS }
  );
  return response.data;
}

/**
 * Simulates an inbound WhatsApp message by posting to the Make.com webhook.
 * Constructs a payload matching the 360dialog / WhatsApp Cloud API webhook format.
 *
 * @param {string}  fromPhone   - Sender phone in +44 format
 * @param {string}  messageText - Message body text
 * @param {object}  options     - Optional fields: mediaUrl, mediaType, messageId
 * @returns {object}            - Webhook response
 */
async function simulateWhatsAppMessage(fromPhone, messageText, options = {}) {
  const messageId = options.messageId || `wamid.test_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
  const timestamp = Math.floor(Date.now() / 1000).toString();

  const messagePayload = {
    from: fromPhone.replace('+', ''),
    id: messageId,
    timestamp,
    type: options.mediaType || 'text',
  };

  if (options.mediaType === 'image') {
    messagePayload.image = {
      caption: messageText,
      mime_type: 'image/jpeg',
      sha256: 'test_sha256_hash',
      id: `media_${Date.now()}`,
    };
    if (options.mediaUrl) {
      messagePayload.image.url = options.mediaUrl;
    }
  } else {
    messagePayload.text = { body: messageText };
  }

  const webhookPayload = {
    object: 'whatsapp_business_account',
    entry: [
      {
        id: CONFIG.whatsappPhoneNumberId,
        changes: [
          {
            value: {
              messaging_product: 'whatsapp',
              metadata: {
                display_phone_number: '442071234567',
                phone_number_id: CONFIG.whatsappPhoneNumberId,
              },
              contacts: [
                {
                  profile: { name: 'Test User' },
                  wa_id: fromPhone.replace('+', ''),
                },
              ],
              messages: [messagePayload],
            },
            field: 'messages',
          },
        ],
      },
    ],
  };

  const response = await axios.post(CONFIG.makeWebhookUrl, webhookPayload, {
    headers: { 'Content-Type': 'application/json' },
    timeout: 15000,
  });

  return { response, messageId };
}

/**
 * Polls Airtable until a record matching the filter appears or timeout is reached.
 * @param {string} tableName     - Airtable table name
 * @param {string} filterFormula - Airtable filter formula
 * @param {number} timeoutMs     - Maximum wait time in ms
 * @param {number} intervalMs    - Polling interval in ms
 * @returns {object|null}        - First matching record or null
 */
async function pollForRecord(tableName, filterFormula, timeoutMs = CONFIG.pollingTimeoutMs, intervalMs = CONFIG.pollingIntervalMs) {
  const startTime = Date.now();
  while (Date.now() - startTime < timeoutMs) {
    const records = await findAirtableRecords(tableName, filterFormula, 1);
    if (records.length > 0) {
      return records[0];
    }
    await sleep(intervalMs);
  }
  return null;
}

/**
 * Polls an existing Airtable record until a field matches an expected value.
 * @param {string} tableName     - Airtable table name
 * @param {string} recordId      - Record ID to watch
 * @param {string} fieldName     - Field name to check
 * @param {*}      expectedValue - Value to wait for
 * @param {number} timeoutMs     - Maximum wait time in ms
 * @returns {object|null}        - Record with matching field value or null
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
 * Sleeps for a given number of milliseconds.
 * @param {number} ms - Milliseconds to sleep
 */
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Generates a unique test marker for correlating test messages to records.
 * @returns {string} - Unique marker string
 */
function generateTestMarker() {
  return `SFTEST_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

// ─── Test Suite ─────────────────────────────────────────────────────────────────

describe('Intake Flow', function () {
  this.timeout(30000);

  // Ensure required configuration is present
  before(function () {
    const requiredVars = ['AIRTABLE_API_KEY', 'AIRTABLE_BASE_ID', 'MAKE_WEBHOOK_URL_SCENARIO_A'];
    const missing = requiredVars.filter((v) => !process.env[v]);
    if (missing.length > 0) {
      this.skip();
      console.warn(`Skipping Intake Flow tests: missing env vars: ${missing.join(', ')}`);
    }
  });

  // Clean up all records created during testing
  after(async function () {
    this.timeout(60000);
    const tables = [
      { name: 'Interaction_Logs', ids: createdRecordIds.interactionLogs },
      { name: 'Work_Items', ids: createdRecordIds.workItems },
      { name: 'People', ids: createdRecordIds.people },
    ];
    for (const table of tables) {
      for (const id of table.ids) {
        try {
          await deleteAirtableRecord(table.name, id);
        } catch (err) {
          // Record may already have been deleted; log and continue
          console.warn(`Cleanup: failed to delete ${table.name}/${id}: ${err.message}`);
        }
      }
    }
  });

  // ── Clear Maintenance Request ───────────────────────────────────────────────

  describe('Clear Maintenance Requests', function () {
    it('should create a Work_Item from a clear maintenance request', async function () {
      const marker = generateTestMarker();
      const messageText = `${TEST_MESSAGES.clearRequest.text} [${marker}]`;

      // 1. Send the WhatsApp message
      const { messageId } = await simulateWhatsAppMessage(TEST_PHONE_KNOWN, messageText);
      expect(messageId).to.be.a('string');

      // 2. Poll for the Work_Item to appear
      const workItem = await pollForRecord(
        'Work_Items',
        `SEARCH("${marker}", {description})`
      );
      expect(workItem, 'Work_Item should be created from a clear maintenance request').to.not.be.null;
      createdRecordIds.workItems.push(workItem.id);

      // 3. Validate initial state
      expect(workItem.fields.current_state).to.be.oneOf(['INTAKE', 'ASSESSMENT']);

      // 4. Validate LLM-extracted fields
      expect(workItem.fields.title).to.be.a('string').and.to.have.length.greaterThan(5);
      expect(workItem.fields.description).to.include(marker);

      // 5. Validate discipline detection
      expect(workItem.fields.discipline_required).to.equal(TEST_MESSAGES.clearRequest.expectedDiscipline);

      // 6. Validate urgency classification
      expect(workItem.fields.urgency).to.equal(TEST_MESSAGES.clearRequest.expectedUrgency);

      // 7. Validate source message linkage
      expect(workItem.fields.source_message_id).to.equal(messageId);

      // 8. Validate LLM confidence is above the clarification threshold
      expect(workItem.fields.llm_confidence).to.be.a('number');
      expect(workItem.fields.llm_confidence).to.be.at.least(0.70);
    });

    it('should populate location fields from message content', async function () {
      const marker = generateTestMarker();
      const messageText = `There is a leak in the 2nd floor WC of Meridian House. [${marker}]`;

      const { messageId } = await simulateWhatsAppMessage(TEST_PHONE_KNOWN, messageText);
      expect(messageId).to.be.a('string');

      const workItem = await pollForRecord(
        'Work_Items',
        `SEARCH("${marker}", {description})`
      );
      expect(workItem, 'Work_Item should be created').to.not.be.null;
      createdRecordIds.workItems.push(workItem.id);

      // Validate extracted location data
      expect(workItem.fields.location_building).to.be.a('string');
      expect(workItem.fields.location_floor).to.be.a('string');
      expect(workItem.fields.location_area).to.be.a('string');
    });
  });

  // ── Emergency Routing ─────────────────────────────────────────────────────────

  describe('Emergency Routing', function () {
    it('should route emergency messages to immediate assignment', async function () {
      const marker = generateTestMarker();
      const messageText = `${TEST_MESSAGES.emergency.text} [${marker}]`;

      const { messageId } = await simulateWhatsAppMessage(TEST_PHONE_KNOWN, messageText);
      expect(messageId).to.be.a('string');

      // Poll for Work_Item creation
      const workItem = await pollForRecord(
        'Work_Items',
        `SEARCH("${marker}", {description})`
      );
      expect(workItem, 'Emergency Work_Item should be created').to.not.be.null;
      createdRecordIds.workItems.push(workItem.id);

      // Validate emergency classification
      expect(workItem.fields.urgency).to.equal('EMERGENCY');
      expect(workItem.fields.discipline_required).to.equal(TEST_MESSAGES.emergency.expectedDiscipline);

      // Emergency items should bypass normal queue and move to ASSESSMENT or ASSIGNED
      expect(workItem.fields.current_state).to.be.oneOf(['ASSESSMENT', 'ASSIGNED']);

      // SLA deadline should be set and tight (within 4 hours for emergency)
      if (workItem.fields.sla_due_at) {
        const slaDue = new Date(workItem.fields.sla_due_at);
        const now = new Date();
        const hoursUntilDue = (slaDue - now) / (1000 * 60 * 60);
        expect(hoursUntilDue).to.be.at.most(4);
      }

      // Verify an outbound notification was logged (to engineer/supervisor)
      await sleep(3000);
      const notifications = await findAirtableRecords(
        'Interaction_Logs',
        `AND({direction} = "OUTBOUND", SEARCH("${marker}", {message_content}))`,
        5
      );
      // At least one notification should have been sent
      expect(notifications.length).to.be.at.least(1);
      notifications.forEach((n) => createdRecordIds.interactionLogs.push(n.id));
    });
  });

  // ── Clarification Flow ────────────────────────────────────────────────────────

  describe('Clarification Flow', function () {
    it('should request clarification for vague messages', async function () {
      const marker = generateTestMarker();
      const messageText = `${TEST_MESSAGES.vagueMessage.text} [${marker}]`;

      const { messageId } = await simulateWhatsAppMessage(TEST_PHONE_KNOWN, messageText);
      expect(messageId).to.be.a('string');

      // Poll for Work_Item
      const workItem = await pollForRecord(
        'Work_Items',
        `SEARCH("${marker}", {description})`
      );
      expect(workItem, 'Work_Item should be created even for vague messages').to.not.be.null;
      createdRecordIds.workItems.push(workItem.id);

      // Should be in CLARIFICATION state
      expect(workItem.fields.current_state).to.equal('CLARIFICATION');

      // LLM confidence should be below the threshold
      expect(workItem.fields.llm_confidence).to.be.a('number');
      expect(workItem.fields.llm_confidence).to.be.below(0.70);

      // Routing decision should indicate clarification needed
      expect(workItem.fields.routing_decision).to.equal('NEEDS_CLARIFICATION');

      // Verify a clarification question was sent via WhatsApp
      await sleep(3000);
      const outbound = await findAirtableRecords(
        'Interaction_Logs',
        `AND({direction} = "OUTBOUND", {channel} = "WHATSAPP", SEARCH("${marker}", {message_content}))`,
        5
      );
      // There should be at least one outbound clarification message
      if (outbound.length > 0) {
        outbound.forEach((n) => createdRecordIds.interactionLogs.push(n.id));
        expect(outbound[0].fields.message_content).to.be.a('string');
        expect(outbound[0].fields.message_content.length).to.be.greaterThan(10);
      }
    });
  });

  // ── Image Messages ────────────────────────────────────────────────────────────

  describe('Image Messages', function () {
    it('should handle image messages with captions', async function () {
      const marker = generateTestMarker();
      const captionText = `${TEST_MESSAGES.imageCaption.text} [${marker}]`;

      const { messageId } = await simulateWhatsAppMessage(
        TEST_PHONE_KNOWN,
        captionText,
        {
          mediaUrl: TEST_MESSAGES.imageCaption.mediaUrl,
          mediaType: 'image',
        }
      );
      expect(messageId).to.be.a('string');

      // Poll for Work_Item
      const workItem = await pollForRecord(
        'Work_Items',
        `SEARCH("${marker}", {description})`
      );
      expect(workItem, 'Work_Item should be created from an image message').to.not.be.null;
      createdRecordIds.workItems.push(workItem.id);

      // Validate fields
      expect(workItem.fields.title).to.be.a('string').and.to.have.length.greaterThan(3);
      expect(workItem.fields.description).to.include(marker);

      // Verify the interaction log recorded the image type
      const interaction = await pollForRecord(
        'Interaction_Logs',
        `AND({whatsapp_message_id} = "${messageId}", {message_type} = "IMAGE")`
      );
      if (interaction) {
        createdRecordIds.interactionLogs.push(interaction.id);
        expect(interaction.fields.message_type).to.equal('IMAGE');
        expect(interaction.fields.media_url).to.be.a('string');
      }
    });
  });

  // ── Deduplication ─────────────────────────────────────────────────────────────

  describe('Deduplication', function () {
    it('should deduplicate repeated messages', async function () {
      const marker = generateTestMarker();
      const messageText = `${TEST_MESSAGES.duplicateMessage.text} [${marker}]`;

      // Use a fixed messageId to simulate the same message arriving twice
      const fixedMessageId = `wamid.dedup_test_${Date.now()}`;

      // Send the message the first time
      await simulateWhatsAppMessage(TEST_PHONE_KNOWN, messageText, { messageId: fixedMessageId });

      // Wait for initial processing
      await sleep(5000);

      // Send the same message again (same whatsapp_message_id)
      await simulateWhatsAppMessage(TEST_PHONE_KNOWN, messageText, { messageId: fixedMessageId });

      // Wait for any secondary processing
      await sleep(5000);

      // Check that only one Work_Item was created
      const workItems = await findAirtableRecords(
        'Work_Items',
        `SEARCH("${marker}", {description})`,
        10
      );

      expect(workItems.length).to.equal(1, 'Duplicate messages should not create multiple Work_Items');
      workItems.forEach((wi) => createdRecordIds.workItems.push(wi.id));

      // Also verify only one inbound interaction log with this messageId
      const interactions = await findAirtableRecords(
        'Interaction_Logs',
        `{whatsapp_message_id} = "${fixedMessageId}"`,
        10
      );
      expect(interactions.length).to.equal(1, 'Duplicate messages should not create multiple Interaction_Logs');
      interactions.forEach((il) => createdRecordIds.interactionLogs.push(il.id));
    });
  });

  // ── Unknown Sender Handling ───────────────────────────────────────────────────

  describe('Unknown Sender Handling', function () {
    it('should create Person record for unknown sender', async function () {
      const marker = generateTestMarker();
      const messageText = `The lights are flickering in the main stairwell at Crown Court Apartments. [${marker}]`;

      // Ensure no Person record exists for the unknown number
      const existingPeople = await findAirtableRecords(
        'People',
        `{whatsapp_number} = "${TEST_PHONE_UNKNOWN}"`
      );
      // Remove any stale test records first
      for (const person of existingPeople) {
        try {
          await deleteAirtableRecord('People', person.id);
        } catch (err) {
          // Allow deletion failures for records potentially linked elsewhere
        }
      }

      // Send from unknown number
      const { messageId } = await simulateWhatsAppMessage(TEST_PHONE_UNKNOWN, messageText);
      expect(messageId).to.be.a('string');

      // Wait for processing to complete
      await sleep(5000);

      // Verify a Person record was created for the unknown sender
      const newPeople = await findAirtableRecords(
        'People',
        `{whatsapp_number} = "${TEST_PHONE_UNKNOWN}"`
      );
      expect(newPeople.length).to.be.at.least(1, 'A Person record should be created for unknown senders');
      newPeople.forEach((p) => createdRecordIds.people.push(p.id));

      const newPerson = newPeople[0];
      expect(newPerson.fields.whatsapp_number).to.equal(TEST_PHONE_UNKNOWN);
      expect(newPerson.fields.role).to.equal('TENANT');
      expect(newPerson.fields.is_active).to.equal(true);

      // Verify a Work_Item was also created and linked to the new person
      const workItem = await pollForRecord(
        'Work_Items',
        `SEARCH("${marker}", {description})`
      );
      expect(workItem, 'Work_Item should be created even for unknown senders').to.not.be.null;
      createdRecordIds.workItems.push(workItem.id);

      // reported_by should link to the newly created person
      if (workItem.fields.reported_by && workItem.fields.reported_by.length > 0) {
        expect(workItem.fields.reported_by[0]).to.equal(newPerson.id);
      }
    });
  });

  // ── LLM Extraction Validation ─────────────────────────────────────────────────

  describe('LLM Extraction', function () {
    it('should extract structured data via LLM and store as JSON', async function () {
      const marker = generateTestMarker();
      const messageText = `The boiler in flat 12A at Wellington Court is making a loud banging noise and leaking water from the pressure valve. It is a Vaillant ecoTEC Plus. [${marker}]`;

      await simulateWhatsAppMessage(TEST_PHONE_KNOWN, messageText);

      const workItem = await pollForRecord(
        'Work_Items',
        `SEARCH("${marker}", {description})`
      );
      expect(workItem, 'Work_Item should be created').to.not.be.null;
      createdRecordIds.workItems.push(workItem.id);

      // llm_extracted_data should contain valid JSON
      expect(workItem.fields.llm_extracted_data).to.be.a('string');
      const extractedData = JSON.parse(workItem.fields.llm_extracted_data);
      expect(extractedData).to.be.an('object');

      // Should have identified the relevant issue type, appliance, and location
      expect(extractedData).to.have.property('issue_type');
      expect(extractedData).to.have.property('location');

      // Confidence should be high for a detailed message
      expect(workItem.fields.llm_confidence).to.be.at.least(0.80);
    });

    it('should correctly identify discipline from message context', async function () {
      const testCases = [
        {
          text: 'Power socket in the boardroom sparking when anything is plugged in',
          expected: 'ELECTRICAL',
        },
        {
          text: 'Air conditioning unit on the 4th floor blowing warm air, needs servicing',
          expected: 'HVAC',
        },
        {
          text: 'Fire alarm panel showing a fault on zone 3, east wing',
          expected: 'FIRE_SAFETY',
        },
      ];

      for (const testCase of testCases) {
        const marker = generateTestMarker();
        const messageText = `${testCase.text} [${marker}]`;

        await simulateWhatsAppMessage(TEST_PHONE_KNOWN, messageText);

        const workItem = await pollForRecord(
          'Work_Items',
          `SEARCH("${marker}", {description})`
        );
        if (workItem) {
          createdRecordIds.workItems.push(workItem.id);
          expect(workItem.fields.discipline_required).to.equal(
            testCase.expected,
            `Expected discipline ${testCase.expected} for message: "${testCase.text}"`
          );
        }
      }
    });
  });

  // ── Notifications ─────────────────────────────────────────────────────────────

  describe('Notifications', function () {
    it('should send acknowledgement to reporter after work item creation', async function () {
      const marker = generateTestMarker();
      const messageText = `Toilet in the ground floor gents is blocked and overflowing at Broadgate Tower, EC2M 1QS. [${marker}]`;

      const { messageId } = await simulateWhatsAppMessage(TEST_PHONE_KNOWN, messageText);

      // Wait for work item creation and acknowledgement processing
      const workItem = await pollForRecord(
        'Work_Items',
        `SEARCH("${marker}", {description})`
      );
      expect(workItem, 'Work_Item should be created').to.not.be.null;
      createdRecordIds.workItems.push(workItem.id);

      // Wait a bit more for notification delivery
      await sleep(5000);

      // Find outbound messages sent to the reporter
      const outboundToReporter = await findAirtableRecords(
        'Interaction_Logs',
        `AND({direction} = "OUTBOUND", {channel} = "WHATSAPP")`,
        20
      );

      // Filter for messages that reference the work item or marker
      const acknowledgements = outboundToReporter.filter((log) => {
        const content = log.fields.message_content || '';
        return content.includes(marker) || (
          log.fields.work_item_id &&
          log.fields.work_item_id.includes &&
          log.fields.work_item_id.includes(workItem.id)
        );
      });

      acknowledgements.forEach((a) => createdRecordIds.interactionLogs.push(a.id));

      // At minimum an acknowledgement should be sent
      expect(acknowledgements.length).to.be.at.least(1, 'Reporter should receive an acknowledgement');
    });

    it('should notify assigned engineer for non-emergency work items', async function () {
      const marker = generateTestMarker();
      const messageText = `Door handle broken on the main entrance to Cabot Square Office, E14 4QT. [${marker}]`;

      await simulateWhatsAppMessage(TEST_PHONE_KNOWN, messageText);

      const workItem = await pollForRecord(
        'Work_Items',
        `SEARCH("${marker}", {description})`
      );
      expect(workItem).to.not.be.null;
      createdRecordIds.workItems.push(workItem.id);

      // If the work item gets assigned, check for an engineer notification
      if (workItem.fields.current_state === 'ASSIGNED' && workItem.fields.assigned_engineer_id) {
        await sleep(3000);

        const engineerNotifications = await findAirtableRecords(
          'Interaction_Logs',
          `AND({direction} = "OUTBOUND", {work_item_id} = "${workItem.id}")`,
          10
        );

        engineerNotifications.forEach((n) => createdRecordIds.interactionLogs.push(n.id));

        // Should have sent at least one notification regarding this assignment
        expect(engineerNotifications.length).to.be.at.least(1,
          'Assigned engineer should be notified about the work item');
      }
    });
  });

  // ── State Transitions ─────────────────────────────────────────────────────────

  describe('State Transitions', function () {
    it('should transition from INTAKE to ASSESSMENT', async function () {
      const marker = generateTestMarker();
      const messageText = `Heating radiator in conference room B is cold and not warming up, Canary Wharf Tower, E14 5AB. [${marker}]`;

      await simulateWhatsAppMessage(TEST_PHONE_KNOWN, messageText);

      // Wait for processing through INTAKE
      await sleep(3000);

      const workItem = await pollForRecord(
        'Work_Items',
        `SEARCH("${marker}", {description})`
      );
      expect(workItem).to.not.be.null;
      createdRecordIds.workItems.push(workItem.id);

      // After LLM processing, item should have moved past INTAKE
      expect(workItem.fields.current_state).to.be.oneOf(
        ['ASSESSMENT', 'ASSIGNED', 'CLARIFICATION'],
        'Work item should transition out of INTAKE after LLM processing'
      );

      // State history should contain the transition record
      if (workItem.fields.state_history) {
        const stateHistory = JSON.parse(workItem.fields.state_history);
        expect(stateHistory).to.be.an('array');
        expect(stateHistory.length).to.be.at.least(1);

        const firstTransition = stateHistory[0];
        expect(firstTransition).to.have.property('from_state', 'INTAKE');
        expect(firstTransition).to.have.property('to_state');
        expect(firstTransition).to.have.property('timestamp');
      }
    });

    it('should transition from ASSESSMENT to ASSIGNED', async function () {
      const marker = generateTestMarker();
      const messageText = `Water dripping from ceiling tiles in the server room, 2nd floor, Palmerston House, SW1A 2AA. Urgent before it damages equipment. [${marker}]`;

      await simulateWhatsAppMessage(TEST_PHONE_KNOWN, messageText);

      // Poll with extended timeout for ASSIGNED state
      const workItem = await pollForRecord(
        'Work_Items',
        `AND(SEARCH("${marker}", {description}), OR({current_state} = "ASSIGNED", {current_state} = "ASSESSMENT"))`,
        CONFIG.pollingTimeoutMs
      );
      expect(workItem).to.not.be.null;
      createdRecordIds.workItems.push(workItem.id);

      // If in ASSESSMENT, wait for it to progress to ASSIGNED
      if (workItem.fields.current_state === 'ASSESSMENT') {
        const assignedItem = await pollForFieldValue(
          'Work_Items',
          workItem.id,
          'current_state',
          'ASSIGNED',
          15000
        );

        if (assignedItem) {
          expect(assignedItem.fields.current_state).to.equal('ASSIGNED');

          // Should have an engineer or contractor assigned
          const hasAssignment =
            (assignedItem.fields.assigned_engineer_id && assignedItem.fields.assigned_engineer_id.length > 0) ||
            (assignedItem.fields.contractor_id && assignedItem.fields.contractor_id.length > 0);
          expect(hasAssignment).to.be.true;

          // Routing decision should be set
          expect(assignedItem.fields.routing_decision).to.be.oneOf([
            'INTERNAL_ENGINEER',
            'EXTERNAL_CONTRACTOR',
          ]);
        }
      }
    });
  });

  // ── Full Lifecycle ────────────────────────────────────────────────────────────

  describe('Full Lifecycle', function () {
    it('should transition through full lifecycle', async function () {
      this.timeout(120000);

      const marker = generateTestMarker();
      const messageText = `Broken window latch on 1st floor, room 105, at Kingsway House, WC2B 6SE. Window will not close properly. [${marker}]`;

      // Step 1: INTAKE - Send the WhatsApp message
      const { messageId } = await simulateWhatsAppMessage(TEST_PHONE_KNOWN, messageText);
      expect(messageId).to.be.a('string');

      // Step 2: Wait for Work_Item creation (INTAKE or ASSESSMENT)
      const workItem = await pollForRecord(
        'Work_Items',
        `SEARCH("${marker}", {description})`,
        CONFIG.pollingTimeoutMs
      );
      expect(workItem, 'Work_Item should be created').to.not.be.null;
      createdRecordIds.workItems.push(workItem.id);

      const workItemId = workItem.id;

      // Step 3: Manually advance to ASSIGNED if not already there
      let currentRecord = await getAirtableRecord('Work_Items', workItemId);
      if (!['ASSIGNED', 'IN_PROGRESS'].includes(currentRecord.fields.current_state)) {
        await updateAirtableRecord('Work_Items', workItemId, {
          current_state: 'ASSIGNED',
          routing_decision: 'INTERNAL_ENGINEER',
          state_started_at: new Date().toISOString(),
          state_history: JSON.stringify([
            {
              from_state: currentRecord.fields.current_state,
              to_state: 'ASSIGNED',
              trigger: 'integration_test',
              timestamp: new Date().toISOString(),
              actor_id: 'test_runner',
              notes: 'Automated lifecycle test advancement',
            },
          ]),
        });
        await sleep(2000);
      }

      // Step 4: Advance to IN_PROGRESS
      await updateAirtableRecord('Work_Items', workItemId, {
        current_state: 'IN_PROGRESS',
        state_started_at: new Date().toISOString(),
      });
      await sleep(2000);

      currentRecord = await getAirtableRecord('Work_Items', workItemId);
      expect(currentRecord.fields.current_state).to.equal('IN_PROGRESS');

      // Step 5: Advance to VERIFICATION (work completed, pending check)
      await updateAirtableRecord('Work_Items', workItemId, {
        current_state: 'VERIFICATION',
        completion_notes: 'Window latch replaced with new ironmongery. Tested and closing correctly.',
        completion_evidence_url: 'https://staging-media.safeflow.io/test/window-fixed.jpg',
        state_started_at: new Date().toISOString(),
      });
      await sleep(2000);

      currentRecord = await getAirtableRecord('Work_Items', workItemId);
      expect(currentRecord.fields.current_state).to.equal('VERIFICATION');
      expect(currentRecord.fields.completion_notes).to.include('Window latch replaced');

      // Step 6: Advance to CLOSED
      const closedAt = new Date().toISOString();
      await updateAirtableRecord('Work_Items', workItemId, {
        current_state: 'CLOSED',
        actual_cost: 85.00,
        closed_at: closedAt,
        state_started_at: closedAt,
      });
      await sleep(2000);

      currentRecord = await getAirtableRecord('Work_Items', workItemId);
      expect(currentRecord.fields.current_state).to.equal('CLOSED');
      expect(currentRecord.fields.closed_at).to.be.a('string');
      expect(currentRecord.fields.actual_cost).to.equal(85.00);

      // Step 7: Validate the full state history was recorded
      if (currentRecord.fields.state_history) {
        const history = JSON.parse(currentRecord.fields.state_history);
        expect(history).to.be.an('array');
        // Should have at least one transition recorded
        expect(history.length).to.be.at.least(1);
      }
    });
  });

  // ── Error Handling ────────────────────────────────────────────────────────────

  describe('Error Handling', function () {
    it('should reject webhook calls with malformed payloads', async function () {
      try {
        const response = await axios.post(
          CONFIG.makeWebhookUrl,
          { invalid: 'payload', missing: 'required_fields' },
          {
            headers: { 'Content-Type': 'application/json' },
            timeout: 10000,
            validateStatus: () => true,
          }
        );
        // Depending on Make.com configuration, this might return 200 (accepted but no processing)
        // or 400/422. Either is acceptable as long as no Work_Item is created.
        expect(response.status).to.be.oneOf([200, 400, 422]);
      } catch (err) {
        // Connection refused or timeout is also acceptable for invalid payloads
        expect(err.code).to.be.oneOf(['ECONNREFUSED', 'ETIMEDOUT', 'ECONNRESET']);
      }
    });

    it('should handle empty message body gracefully', async function () {
      const marker = generateTestMarker();

      try {
        await simulateWhatsAppMessage(TEST_PHONE_KNOWN, '', { messageId: `wamid.empty_${marker}` });
      } catch (err) {
        // May be rejected at the webhook level; that is acceptable
      }

      // Wait briefly then verify no Work_Item was created for an empty message
      await sleep(5000);
      const workItems = await findAirtableRecords(
        'Work_Items',
        `{source_message_id} = "wamid.empty_${marker}"`,
        5
      );
      expect(workItems.length).to.equal(0, 'Empty messages should not create Work_Items');
    });

    it('should handle extremely long messages without crashing', async function () {
      const marker = generateTestMarker();
      const longMessage = `Issue report: ${'The heating system in the building is not working properly and needs attention. '.repeat(50)}[${marker}]`;

      try {
        const { messageId } = await simulateWhatsAppMessage(TEST_PHONE_KNOWN, longMessage);
        expect(messageId).to.be.a('string');

        // Should either create a work item or handle gracefully
        await sleep(8000);
        const workItems = await findAirtableRecords(
          'Work_Items',
          `SEARCH("${marker}", {description})`,
          5
        );
        // Work item creation is acceptable; the test verifies no crash
        workItems.forEach((wi) => createdRecordIds.workItems.push(wi.id));
      } catch (err) {
        // Rejection due to payload size is acceptable
        expect(err.response ? err.response.status : err.code).to.satisfy(
          (val) => [413, 400, 'ECONNRESET'].includes(val),
          'Should reject with appropriate error, not crash'
        );
      }
    });

    it('should handle concurrent messages from the same sender', async function () {
      const marker1 = generateTestMarker();
      const marker2 = generateTestMarker();

      const message1 = `Broken lock on fire exit door, ground floor. [${marker1}]`;
      const message2 = `Faulty light switch in the reception area, keeps tripping. [${marker2}]`;

      // Send two messages simultaneously from the same phone number
      const [result1, result2] = await Promise.all([
        simulateWhatsAppMessage(TEST_PHONE_KNOWN, message1),
        simulateWhatsAppMessage(TEST_PHONE_KNOWN, message2),
      ]);

      expect(result1.messageId).to.be.a('string');
      expect(result2.messageId).to.be.a('string');
      expect(result1.messageId).to.not.equal(result2.messageId);

      // Wait for processing
      await sleep(8000);

      // Both should create separate Work_Items
      const items1 = await findAirtableRecords(
        'Work_Items',
        `SEARCH("${marker1}", {description})`,
        5
      );
      const items2 = await findAirtableRecords(
        'Work_Items',
        `SEARCH("${marker2}", {description})`,
        5
      );

      items1.forEach((wi) => createdRecordIds.workItems.push(wi.id));
      items2.forEach((wi) => createdRecordIds.workItems.push(wi.id));

      expect(items1.length).to.equal(1, 'First concurrent message should create exactly one Work_Item');
      expect(items2.length).to.equal(1, 'Second concurrent message should create exactly one Work_Item');

      // They should be different records
      if (items1.length > 0 && items2.length > 0) {
        expect(items1[0].id).to.not.equal(items2[0].id);
      }
    });
  });
});
