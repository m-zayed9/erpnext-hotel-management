import frappe
from frappe import _

def validate_purchase_invoice(doc, method):
    frappe.logger().info("Validating Purchase Invoice: {}".format(doc.name))
    
    # Check if this is a hotel purchase
    is_hotel_purchase = doc.get('custom_is_hotel_purchase')
    
    if is_hotel_purchase:
        # Fields to validate
        required_fields = [
            'custom_room_quantity',
            'custom_nights_count',
            'custom_start_date',
            'custom_end_date'
        ]
        
        # Check each item in the items table
        for idx, item in enumerate(doc.items):
            missing_fields = []
            
            # Check if any required field is missing
            for field in required_fields:
                if not item.get(field):
                    missing_fields.append(field.replace('custom_', '').replace('_', ' ').title())
            
            # If any field is missing, throw an error
            if missing_fields:
                field_list = ", ".join(missing_fields)
                frappe.throw(
                    _("Row #{0}: {1} {2} required for hotel purchases.").format(
                        idx+1, 
                        field_list,
                        'is' if len(missing_fields) == 1 else 'are'
                    )
                )