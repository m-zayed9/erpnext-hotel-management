// your_app_name/public/js/booking.js

frappe.ui.form.on('Booking', {
    validate: function(frm) {
        // Auto-calculate total before saving
        calculate_total(frm);
    }
});

// Child table (Booking Room) handlers
frappe.ui.form.on('Booking Room', {
    room_id: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if(row.room_id && row.booking_date) {
            fetch_room_price(frm, row);
        }
    },
    booking_date: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if(row.room_id && row.booking_date) {
            fetch_room_price(frm, row);
        }
    },
    price: function(frm, cdt, cdn) {
        calculate_total(frm);
    },
    quantity: function(frm, cdt, cdn) {
        calculate_total(frm);
    },
    booking_rooms_add: function(frm, cdt, cdn) {
        calculate_total(frm);
    },
    booking_rooms_remove: function(frm, cdt, cdn) {
        calculate_total(frm);
    }
});

// Function to calculate the total price based on all room bookings
function calculate_total(frm) {
    let total = 0;
    
    if(frm.doc.booking_rooms && frm.doc.booking_rooms.length > 0) {
        frm.doc.booking_rooms.forEach(function(room_row) {
            if(room_row.price && room_row.quantity) {
                total += flt(room_row.price) * flt(room_row.quantity);
            }
        });
    }
    
    frm.set_value('total_price', total);
    frm.refresh_field('total_price');
}

function fetch_room_price(frm, row) {
    console.log(row.booking_date , row.room_id)
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Room Price",
            filters: {
                room_id: row.room_id,
                start_date: ["<=", row.booking_date],
                end_date: [">=", row.booking_date]
            },
            fields: ["price_per_night"]
        },
        callback: function(response) {
            if(response.message && response.message.length > 0) {
                console.log(response.message)
                frappe.model.set_value(row.doctype, row.name, "price", response.message[0].price_per_night);
                frm.refresh_field("booking_rooms");
                calculate_total(frm);
            } else {
                frappe.model.set_value(row.doctype, row.name, "price", 0);
                frm.refresh_field("booking_rooms");
            }
        }
    });
}


