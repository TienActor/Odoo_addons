from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class BKGProcessEPR(models.TransientModel):
    """ Model for storing purchase requisition """
    _name = 'bkg.process.epr'
    
    epr_id = fields.Many2one('employee.purchase.requisition', required=True)
    
    def action_fetch_data(self):
        list_arr = []
        if len(self) == 1:
            epr_id = self.epr_id
            root_id = 0
            ## root parent
            list_arr.append({'name': epr_id.name, 'id': root_id})
            ## Bỏ những phiếu IT có mã PO hoặc những thiếu PO của EPR vào array
            po_ids = self.env['purchase.order'].search([
            ('requisition_order', '=', self.name)])
            epr_picking_ids = self.env['stock.picking'].search([
            ('requisition_order', '=', self.name), ('bkg_purchase_order_name', '!=', False)])
            stt = 1
            for po_id in po_ids:
                list_arr.append({'name': po_id.name +'(' + po_id.state +')',
                                'parent': root_id, 'id': stt})
                stt += 1
            for epr_picking_id in epr_picking_ids:
                list_arr.append({'name': epr_picking_id.name +'(' + epr_picking_id.state +')',
                                'parent': root_id, 'id': stt})
                stt += 1
        return list_arr
            
                