/**
 * Airtable Automation: Status Change Notification
 *
 * Trigger: When "Status" field changes in "Maintenance Requests" table
 * Action: Sends webhook to Make.com to notify tenant via WhatsApp
 *
 * Setup in Airtable:
 * 1. Automations → Create Automation
 * 2. Trigger: "When a record matches conditions" or "When record updated"
 *    - Table: Maintenance Requests
 *    - Watch field: Status
 * 3. Action: "Run a script" (paste this code)
 * 4. Input variables:
 *    - recordId: Record ID
 *    - reference: {Reference}
 *    - newStatus: {Status}
 *    - tenantName: {Tenant} (lookup → Full Name)
 *    - tenantPhone: {Tenant} (lookup → Phone)
 *    - description: {Description}
 *    - category: {Category}
 */

const config = input.config();

// Validate required inputs
const required = ['recordId', 'reference', 'newStatus', 'tenantPhone', 'tenantName'];
for (const field of required) {
    if (!config[field]) {
        console.error(`Missing required field: ${field}`);
        return;
    }
}

// Status messages — controls which transitions trigger notifications
const STATUS_MESSAGES = {
    'Acknowledged': 'Your request {{reference}} has been acknowledged by our team. We\'re looking into it.',
    'In Progress': 'Good news! Work has started on your request {{reference}} ({{category}}).',
    'Awaiting Parts': 'Your request {{reference}} is waiting for parts to arrive. We\'ll update you when they\'re in.',
    'Scheduled': 'Your maintenance request {{reference}} has been scheduled. You\'ll receive details shortly.',
    'Completed': 'The work on your request {{reference}} has been completed. Please let us know if everything looks good.',
    'Resolved': 'Your request {{reference}} has been marked as resolved. Thank you for your patience!'
};

// Only notify for specific status transitions
if (!STATUS_MESSAGES[config.newStatus]) {
    console.log(`No notification configured for status: ${config.newStatus}`);
    return;
}

// Build notification payload
const payload = {
    notification_type: 'status_update',
    recipient_phone: config.tenantPhone,
    recipient_name: config.tenantName,
    template_name: 'maintenance_status_update',
    template_params: {
        reference: config.reference,
        new_status: config.newStatus,
        category: config.category || 'General',
        details: STATUS_MESSAGES[config.newStatus]
            .replace('{{reference}}', config.reference)
            .replace('{{category}}', config.category || 'General')
    },
    priority: config.newStatus === 'Completed' ? 'high' : 'normal'
};

// Send to Make.com webhook
const WEBHOOK_URL = 'MAKE_NOTIFICATION_WEBHOOK_URL'; // Replace during setup

try {
    const response = await fetch(WEBHOOK_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    if (response.ok) {
        console.log(`Notification sent for ${config.reference} → ${config.newStatus}`);
    } else {
        console.error(`Webhook failed: ${response.status} ${response.statusText}`);
    }
} catch (error) {
    console.error(`Failed to send notification: ${error.message}`);
}
