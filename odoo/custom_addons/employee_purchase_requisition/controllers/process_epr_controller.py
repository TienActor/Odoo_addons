from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request


class ProcessEPRChartController(http.Controller):
    
    @http.route('/epr/action_fetch_data', type='json', auth='user')
    def action_fetch_data(self, epr_id):
        list_arr = []
        epr = request.env['employee.purchase.requisition'].browse(epr_id)
        if epr:
            root_id = 1
            ## root parent
            list_arr.append({'name': epr.name, 'id': root_id, 'parent': 0})
            
            # Bỏ những phiếu IT có mã PO hoặc những thiếu PO của EPR vào array
            stt = 2
            
            ## Internal Transfer
            epr_picking_ids = request.env['stock.picking'].search([
            ('requisition_order', '=', epr.name), ('bkg_purchase_order_name', '=', False)])
            
            for epr_picking_id in epr_picking_ids:
                temp = {
                    'name': epr_picking_id.name,
                    'description': epr_picking_id.state,
                    'parent': root_id, 
                    'id': stt, 
                    'type': 'it', 
                    'type_id': epr_picking_id.id
                }
                status = False
                if epr_picking_id.state == 'done':
                    status = True
                temp['status'] = status
                list_arr.append(temp)
                stt += 1
            
            ## PO
            po_ids = request.env['purchase.order'].search([
            ('requisition_order', '=', epr.name)])
            for po_id in po_ids:
                temp = {
                    'name': po_id.name,
                    'parent': root_id, 
                    'description': po_id.state,
                    'id': stt, 
                    'type': 'po', 
                    'type_id': po_id.id
                }
                status = False
                if po_id.state == 'done':
                    status = True
                temp['status'] = status
                list_arr.append(temp)
                po_index = stt
                stt += 1
                
                po_picking_ids = po_id.picking_ids
                if len(po_picking_ids) == 1:
                    picking_ids = request.env['stock.picking'].search([('bkg_purchase_order_name', '=', po_id.name)])
                    for picking_id in picking_ids:
                        temp = {
                            'name': picking_id.name,
                            'description': picking_id.state,
                            'parent': po_index, 
                            'id': stt, 
                            'type': 'it', 
                            'type_id': picking_id.id
                        }
                        status = False
                        if picking_id.state == 'done':
                            status = True
                        temp['status'] = status
                        list_arr.append(temp)
                        stt += 1
                        
                    temp = {
                        'name': po_picking_ids.name,
                        'parent': po_index, 
                        'description': po_picking_ids.state,
                        'id': stt, 
                        'type': 'it', 
                        'type_id': po_picking_ids.id
                    }
                    status = False
                    if po_picking_ids.state == 'done':
                        status = True
                    temp['status'] = status
                    list_arr.append(temp)
                    stt += 1
                elif len(po_picking_ids) > 1:
                    picking_ids = request.env['stock.picking'].search([('bkg_purchase_order_name', '=', po_id.name)])
                    for picking_id in picking_ids:
                        temp = {
                            'name': picking_id.name,
                            'description': picking_id.state,
                            'parent': po_index, 
                            'id': stt, 
                            'type': 'it', 
                            'type_id': picking_id.id
                        }
                        status = False
                        if picking_id.state == 'done':
                            status = True
                        temp['status'] = status
                        list_arr.append(temp)
                        stt += 1
                    for po_picking_id in po_picking_ids:
                        temp = {
                            'name': po_picking_id.name,
                            'description': po_picking_id.state,
                            'parent': po_index, 
                            'id': stt, 
                            'type': 'it', 
                            'type_id': po_picking_id.id
                        }
                        status = False
                        if po_picking_id.state == 'done':
                            status = True
                        temp['status'] = status
                        list_arr.append(temp)
                        stt += 1
                            
        return list_arr
    
    @http.route('/epr/action_open_window', type='json', auth='user')
    def action_open_window(self, type, type_id):
        action = {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': type_id,
            'target': 'current',
        }
        if type == 'po':
            action['res_model'] = 'purchase.order'
            form_view_id = request.env.ref('purchase.purchase_order_form').id
            action['views'] =[(form_view_id, 'form')]
        elif type == 'it':
            action['res_model'] = 'stock.picking'
            form_view_id = request.env.ref('stock.view_picking_form').id
            action['views'] =[(form_view_id, 'form')]
        
        return action