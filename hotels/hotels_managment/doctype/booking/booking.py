from frappe.model.document import Document
import frappe

class Booking(Document):
    def on_update(self):
        self.create_sales_invoice()
    
    def create_sales_invoice(self):
        try:
            invoice = frappe.new_doc("Sales Invoice")
            invoice.customer = self.customer
            invoice.due_date = frappe.utils.nowdate()
            invoice.set_posting_time = 1
            invoice.posting_date = frappe.utils.nowdate()
            
            for room in self.booking_rooms:
                room_doc = frappe.get_doc("Room", room.room_id)
                invoice.append("items", {
                    "item_code": room_doc.item_id,
                    "qty": room.quantity,
                    "rate": room.price
                })
            
            invoice.insert(ignore_permissions=True)
            invoice.submit()

            self.sales_invoice_id = invoice.name
            self.db_update()

        except Exception as e:
            frappe.throw(f"Failed to create Sales Invoice: {str(e)}")
