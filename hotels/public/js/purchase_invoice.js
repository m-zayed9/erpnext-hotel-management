frappe.ui.form.on('Purchase Invoice', {
    refresh: function(frm) {
        // This runs when the form is loaded/refreshed
        // Initialize any empty fields in existing rows
        if(frm.doc.items && frm.doc.items.length > 0) {
            frm.doc.items.forEach(function(item) {
                handle_empty_fields(frm, item.doctype, item.name);
            });
        }
    }
});

frappe.ui.form.on('Purchase Invoice Item', {
    custom_room_quantity: function(frm, cdt, cdn) {
        handle_empty_fields(frm, cdt, cdn);
        calculate_accepted_qty(frm, cdt, cdn);
    },
    
    custom_nights_count: function(frm, cdt, cdn) {
        handle_empty_fields(frm, cdt, cdn);
        calculate_accepted_qty(frm, cdt, cdn);
    }
});

function handle_empty_fields(frm, cdt, cdn) {
    let item = locals[cdt][cdn];
    
    // Handle empty custom_room_quantity
    if(!item.custom_room_quantity || item.custom_room_quantity === '') {
        frappe.model.set_value(cdt, cdn, 'custom_room_quantity', 0);
    }
    
    // Handle empty custom_nights_count
    if(!item.custom_nights_count || item.custom_nights_count === '') {
        frappe.model.set_value(cdt, cdn, 'custom_nights_count', 0);
    }
}

function calculate_accepted_qty(frm, cdt, cdn) {
    let item = locals[cdt][cdn];
    
    // Check if both custom_room_quantity and custom_nights_count have non-zero values
    if (item.custom_room_quantity && item.custom_nights_count && 
        parseFloat(item.custom_room_quantity) !== 0 && 
        parseFloat(item.custom_nights_count) !== 0) {
        
        // Calculate accepted_qty as the product of custom_room_quantity and custom_nights_count
        let accepted_qty = parseFloat(item.custom_room_quantity) * parseFloat(item.custom_nights_count);
        frappe.model.set_value(cdt, cdn, 'qty', accepted_qty);
        
        // Disable the accepted_qty field
        setTimeout(function() {
            frm.fields_dict.items.grid.grid_rows_by_docname[cdn].toggle_editable('qty', false);
        }, 100);
    } else {
        // If either field is 0 or empty, set accepted_qty to 0 and make it editable
        frappe.model.set_value(cdt, cdn, 'qty', 0);
        
        // Enable the accepted_qty field for manual entry
        setTimeout(function() {
            frm.fields_dict.items.grid.grid_rows_by_docname[cdn].toggle_editable('qty', true);
        }, 100);
    }
}