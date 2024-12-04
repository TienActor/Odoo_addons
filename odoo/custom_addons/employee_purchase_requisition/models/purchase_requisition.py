# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Vishnu P(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
""" Purchase Requisition model"""
import copy
import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import io
import xlsxwriter
import base64
import pytz
import requests
import asyncio

class PurchaseRequisition(models.Model):
    """ Model for storing purchase requisition """
    _name = 'employee.purchase.requisition'
    _description = 'Purchase Requisition'
    _inherit = "mail.thread", "mail.activity.mixin"

    name = fields.Char(string="Reference No", readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Employee',
                                  required=True, help='Employee', default=lambda self: self.env.user.employee_id)
    dept_id = fields.Many2one('hr.department', string='Department',
                              store=True,
                              help='Department', default=lambda self: self.env.user.employee_id.department_id)
    user_id = fields.Many2one('res.users', string='Requisition Responsible',
                              required=True,
                              help='Requisition responsible user')
    requisition_date = fields.Date(string="Requisition Date",
                                   default=lambda self: fields.Date.today(),
                                   help='Date of Requisition')
    receive_date = fields.Date(string="Received Date", readonly=True,
                               help='Receive Date')
    requisition_deadline = fields.Date(string="Requisition Deadline",
                                       help="End date of Purchase requisition")
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company,
                                 help='Company')
    requisition_order_ids = fields.One2many('requisition.order',
                                            'requisition_product_id',
                                            required=True,
                                            copy=True,
                                            tracking=True)
    confirm_id = fields.Many2one('res.users', string='Confirmed By',
                                 default=lambda self: self.env.uid,
                                 readonly=True,
                                 help='User who Confirmed the requisition.')
    manager_id = fields.Many2one('res.users', string='Department Manager',
                                 readonly=True, help='Department Manager')
    requisition_head_id = fields.Many2one('res.users', string='Approved By',
                                          readonly=True,
                                          help='User who approved the requisition.')
    rejected_user_id = fields.Many2one('res.users', string='Rejected By',
                                       readonly=True,
                                       help='user who rejected the requisition')
    confirmed_date = fields.Date(string='Confirmed Date', readonly=True,
                                 help='Date of Requisition Confirmation')
    department_approval_date = fields.Date(string='Department Approval Date',
                                           readonly=True,
                                           help='Department Approval Date')
    approval_date = fields.Date(string='Approved Date', readonly=True,
                                help='Requisition Approval Date')
    reject_date = fields.Date(string='Rejection Date', readonly=True,
                              help='Requisition Rejected Date')
    source_location_id = fields.Many2one('stock.location',
                                         string='Source Location',
                                         help='Source location of requisition.')
    destination_location_id = fields.Many2one('stock.location',
                                              string="Destination Location",
                                              help='Destination location of requisition.')
    delivery_type_id = fields.Many2one('stock.picking.type',
                                       string='Delivery To',
                                       help='Type of Delivery.')
    internal_picking_id = fields.Many2one('stock.picking.type',
                                          string="Internal Picking")
    requisition_description = fields.Text(string="Reason For Requisition")
    purchase_count = fields.Integer(string='Purchase Count')
    internal_transfer_count = fields.Integer(string='Internal Transfer count')
    ##Project stock
    project_id = fields.Many2one('project.project', string='Project', help='Source location of requisition.')
    project_task_id = fields.Many2one('project.task',
                                         string='Project task',
                                         help='project task id.')

    state = fields.Selection(
        [('new', 'New'),
         ('waiting_department_approval', 'Waiting Department Approval'),
         ('waiting_supervisor_approval', 'Waiting Supervisor Approval'),
         ('waiting_head_approval', 'Waiting Head Approval'),
         ('approved', 'Approved'),
         ('purchase_order_created', 'Purchase Order Created'),
         ('received', 'Received'),
         ('cancelled', 'Cancelled')],
        default='new', copy=False, tracking=True)
    
    check_user_group = fields.Boolean(
        compute="_compute_check_user_group"
    )
    
    x_department = fields.Many2one(
        'hr.department', string="Department"
    )
    
    x_requisitionsystem_id = fields.Many2one(
        'x_requisition.system', string="Phân Hệ"
    )
    actual_deadline = fields.Date(string="Actual Deadline",
                                       help="Actual Deadline")
    confirmed_by = fields.Many2one('res.users', string='Confirmed By')
    
    supervisor_approved_id = fields.Many2one('res.users', string='Supervisor Approved By',
                                          readonly=True,
                                          help='User who approved the requisition in supervisor state.')
    supervisor_approval_date = fields.Date(string='Supervisor Approved Date', readonly=True,
                                help='Requisition Approval Date In Supervisor State')
    
    export_pr_binary = fields.Binary()
    export_pr_binary_name = fields.Char()
    bkg_quantity_status = fields.Char(string='Quantity', compute='_compute_bkg_quantity_status' )
    bkg_request_quantity = fields.Float(string='Request Quantity', compute='_compute_bkg_request_quantity')
    bkg_received_quantity = fields.Float(string='Received Quantity', compute='_compute_bkg_received_quantity')
    bkg_warning_qty_status = fields.Selection(
        [('none', 'None'),
         ('two_days_left', 'Two Days Left'),
         ('late', 'Late')], compute='_compute_bkg_warning_qty_status', search = '_search_warning_pr')
    bkg_check_update_po_pickings = fields.Boolean(compute='_compute_bkg_check_update_po_pickings')
    bkg_check_create_po_pickings = fields.Boolean(compute='_compute_bkg_check_create_po_pickings')
    
    @api.depends('state')
    def _compute_bkg_check_update_po_pickings(self):
        for record in self:
            if record.state == 'approved' and (record.env['purchase.order'].search_count([('requisition_order', '=', record.name)]) > 0 or record.env['stock.picking'].search_count([('requisition_order', '=', record.name)]) > 0):
                record.bkg_check_update_po_pickings = True
            else:
                record.bkg_check_update_po_pickings = False
    
    @api.depends('state')
    def _compute_bkg_check_create_po_pickings(self):
        for record in self:
            if record.state == 'approved' and record.env['purchase.order'].search_count([('requisition_order', '=', record.name)]) == 0 and record.env['stock.picking'].search_count([('requisition_order', '=', record.name)]) == 0:
                record.bkg_check_create_po_pickings = True
            else:
                record.bkg_check_create_po_pickings = False
                
    def _search_warning_pr(self, operator, value):
        ids_arr = []
        records = self.env['employee.purchase.requisition'].search([('actual_deadline', '!=', False), ('state', '!=', 'cancelled')])
        for record in records:
            if record.bkg_warning_qty_status in ['two_days_left', 'late']:
                ids_arr.append(record.id)
        return [('id', 'in', ids_arr)]
    
    def action_daily_get_warning_pr_emails(self):
        epr_ids = self.env['employee.purchase.requisition'].search([('actual_deadline', '!=', False), ('state', '!=', 'cancelled')], order='create_date desc')
        mail_template_id = self.env['mail.template'].search([('name', '=', 'BKG_Daily_Warning_PR')])
        if mail_template_id and len(mail_template_id) == 1:
            if epr_ids:
                html = '<table><tr><th>Reference No</th><th>Phân Hệ</th><th>Project</th><th>Employee</th><th>Confirmed Deadline</th><th>Quantity</th></tr>'
                for epr_id in epr_ids:
                    if epr_id.bkg_warning_qty_status:
                        name = epr_id.name
                        x_requisitionsystem_id =''
                        if epr_id.x_requisitionsystem_id: x_requisitionsystem_id = epr_id.x_requisitionsystem_id.x_name
                        project_id = ''
                        if epr_id.project_id: project_id = epr_id.project_id.name
                        employee_id = epr_id.employee_id.name
                        confirmed_deadline = ''
                        if epr_id.actual_deadline: 
                            confirmed_deadline = epr_id.actual_deadline.strftime("%d/%m/%Y")
                        bkg_quantity_status = str(epr_id.bkg_quantity_status)
                        def add_element(string, html):
                            html+='<td>'+string+'</td>'
                            return html
                        html+='<tr>'
                        html = add_element(name, html)
                        html = add_element(x_requisitionsystem_id, html)
                        html = add_element(project_id, html)
                        html = add_element(employee_id, html)
                        html = add_element(confirmed_deadline, html)
                        html = add_element(bkg_quantity_status, html)
                        html+='</tr>'
                html+='</table>'
                new_mail = self.env['bkg.daily.warning.pr.email'].create({
                    'table_html': html
                })
                mail_template_id.send_mail(new_mail.id, force_send=False)
    
    def action_open_bkg_process_epr_view(self):
        process_epr = self.env['bkg.process.epr'].create({'epr_id': self.id})
        return {
            'type': 'ir.actions.act_window',
            'name': 'Process ' + self.name,
            'view_mode': 'form',
            'res_model': 'bkg.process.epr',
            'res_id': process_epr.id,
            'target': 'new'
        }
    
    @api.model
    def _compute_bkg_warning_qty_status(self):
        for record in self:
            status = 'none'
            if record.actual_deadline:
                if (record.actual_deadline - fields.date.today()).days <= 0 and record.bkg_received_quantity != record.bkg_request_quantity:
                    status = 'late'
                if 0 < (record.actual_deadline - fields.date.today()).days < 2 and record.bkg_received_quantity != record.bkg_request_quantity:
                    status = 'two_days_left'
            record.bkg_warning_qty_status = status
    
    @api.model
    def _compute_bkg_request_quantity(self):
        for record in self:
            total_request_qty = 0
            for requisition_order_id in record.requisition_order_ids:
                total_request_qty += requisition_order_id.quantity
            record.bkg_request_quantity = total_request_qty
            
    @api.model
    def _compute_bkg_received_quantity(self):
        for record in self:
            total_received_qty = 0
            # po_ids = record.env['purchase.order'].search([
            # ('requisition_order', '=', record.name)])
            # epr_picking_ids = record.env['stock.picking'].search([
            # ('requisition_order', '=', record.name)])
            # if record.project_id and record.project_id.bkg_stock_info_id:
            #     for po_id in po_ids:
            #         for picking_id in po_id.picking_ids:
            #                 if record.project_id.bkg_stock_info_id.lot_stock_id.id == picking_id.location_dest_id.id and picking_id.state=='done':
            #                     for move_id_without_package in picking_id.move_ids_without_package:
            #                         total_received_qty += move_id_without_package.quantity_done
            #     for picking_id in epr_picking_ids:
            #         if record.project_id.bkg_stock_info_id.lot_stock_id.id == picking_id.location_dest_id.id and picking_id.state=='done':
            #             for move_id_without_package in picking_id.move_ids_without_package:
            #                 total_received_qty += move_id_without_package.quantity_done
            # record.bkg_received_quantity = total_received_qty
            for requisition_order_id in record.requisition_order_ids:
                total_received_qty += requisition_order_id.bkg_received_qty
            record.bkg_received_quantity = total_received_qty
        
    @api.model
    def _compute_bkg_quantity_status(self):
        for record in self:
            record.bkg_quantity_status = str(record.bkg_received_quantity) + '/'+ str(record.bkg_request_quantity)
    
    @api.model       
    def _compute_check_user_group(self):
        self.check_user_group = self.env.user.has_group('employee_purchase_requisition.employee_requisition_manager')

    @api.model
    def create(self, vals):
        """generate purchase requisition sequence"""
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'employee.purchase.requisition') or 'New'
        result = super(PurchaseRequisition, self).create(vals)
        return result

    def action_confirm_requisition(self):
        """confirm purchase requisition"""
        # if self.project_id:
        #     if self.project_id.picking_type_id and self.project_id.location_id and self.project_id.location_dest_id:
        #         self.delivery_type_id = self.project_id.picking_type_id
        #         self.internal_picking_id = self.project_id.picking_type_id
        #         self.source_location_id = self.project_id.location_id
        #         self.destination_location_id = self.project_id.location_dest_id
        #     else:
        #         self.source_location_id = self.employee_id.department_id.department_location_id.id
        #         self.destination_location_id = self.employee_id.employee_location_id.id
        #         self.delivery_type_id = self.source_location_id.warehouse_id.in_type_id.id
        #         self.internal_picking_id = self.source_location_id.warehouse_id.int_type_id.id
        # else:
        #     self.source_location_id = self.employee_id.department_id.department_location_id.id
        #     self.destination_location_id = self.employee_id.employee_location_id.id
        #     self.delivery_type_id = self.source_location_id.warehouse_id.in_type_id.id
        #     self.internal_picking_id = self.source_location_id.warehouse_id.int_type_id.id
        self.write({'state': 'waiting_department_approval'})
        self.confirm_id = self.env.uid
        self.confirmed_date = fields.Date.today()
        
        ## Change requisition type
        rorders = self.requisition_order_ids
        route = self.env['stock.route'].search([('name', 'in',['Manufacture','Sản xuất'])])
        for rorder in rorders:
            if rorder.product_id.name == "Unknown":
                continue
            if route.id in rorder.product_id.product_tmpl_id.route_ids.ids:
                rorder.requisition_type = 'internal_transfer'
            else:    
                if self.source_location_id:
                    stock_quant = self.env['stock.quant'].search([('product_id', '=', rorder.product_id.id), ('location_id', '=', self.source_location_id.id)])
                    if stock_quant.quantity >= rorder.quantity:
                        rorder.requisition_type = 'internal_transfer'
                    else:
                        rorder.requisition_type = 'purchase_order'
                        
    def action_supervisor_approval(self):
        self.write({'state': 'waiting_head_approval'})
        self.supervisor_approved_id = self.env.uid
        self.supervisor_approval_date = fields.Date.today()
    def action_supervisor_cancel(self):
        self.write({'state': 'cancelled'})
        self.rejected_user_id = self.env.uid
        self.reject_date = fields.Date.today()
    def action_department_approval(self):
        rorders = self.requisition_order_ids
        route = self.env['stock.route'].search([('name', 'in',['Manufacture','Sản xuất'])])
        for rorder in rorders:
            if rorder.product_id.name == "Unknown":
                continue
            if rorder.requisition_type:
                continue
            if route.id in rorder.product_id.product_tmpl_id.route_ids.ids:
                rorder.requisition_type = 'internal_transfer'
            else:    
                if self.source_location_id:
                    stock_quant = self.env['stock.quant'].search([('product_id', '=', rorder.product_id.id), ('location_id', '=', self.source_location_id.id)])
                    if stock_quant.quantity >= rorder.quantity:
                        rorder.requisition_type = 'internal_transfer'
                    else:
                        rorder.requisition_type = 'purchase_order'
                        
        """approval from department"""
        
        self.manager_id = self.env.uid
        self.department_approval_date = fields.Date.today()
        self.write({'state': 'waiting_supervisor_approval'})
        # if self.x_requisitionsystem_id and self.x_requisitionsystem_id.x_name.upper().strip() == 'THIẾT BỊ CHÍNH':
        #     self.write({'state': 'waiting_head_approval'})
        # else:
        #     self.write({'state': 'waiting_supervisor_approval'})
        
        # rorders = self.requisition_order_ids
        # route = self.env['stock.route'].search([('name', 'in',['Manufacture','Sản xuất'])])
        # for rorder in rorders:
        #     if rorder.product_id.name == "Unknown":
        #         continue
        #     if rorder.requisition_type:
        #         continue
        #     if route.id in rorder.product_id.product_tmpl_id.route_ids.ids:
        #         rorder.requisition_type = 'internal_transfer'
        #     else:    
        #         if self.source_location_id:
        #             stock_quant = self.env['stock.quant'].search([('product_id', '=', rorder.product_id.id), ('location_id', '=', self.source_location_id.id)])
        #             if stock_quant.quantity >= rorder.quantity:
        #                 rorder.requisition_type = 'internal_transfer'
        #             else:
        #                 rorder.requisition_type = 'purchase_order'

    def action_department_cancel(self):
        """cancellation from department """
        self.write({'state': 'cancelled'})
        self.rejected_user_id = self.env.uid
        self.reject_date = fields.Date.today()

    def action_head_approval(self):
        """approval from department head"""
        self.write({'state': 'approved'})
        self.requisition_head_id = self.env.uid
        self.approval_date = fields.Date.today()
        
        rorders = self.requisition_order_ids
        route = self.env['stock.route'].search([('name', 'in',['Manufacture','Sản xuất'])])
        for rorder in rorders:
            if rorder.product_id.name == "Unknown":
                continue
            if rorder.requisition_type:
                continue
            if route.id in rorder.product_id.product_tmpl_id.route_ids.ids:
                rorder.requisition_type = 'internal_transfer'
            else:    
                if self.source_location_id:
                    stock_quant = self.env['stock.quant'].search([('product_id', '=', rorder.product_id.id), ('location_id', '=', self.source_location_id.id)])
                    if stock_quant.quantity >= rorder.quantity:
                        rorder.requisition_type = 'internal_transfer'
                    else:
                        rorder.requisition_type = 'purchase_order'

    def action_head_cancel(self):
        """cancellation from department head"""
        self.write({'state': 'cancelled'})
        self.rejected_user_id = self.env.uid
        self.reject_date = fields.Date.today()

    def action_create_purchase_order(self):
        for rorder in self.requisition_order_ids:
            if rorder.requisition_type in ['', None, False]:
                raise UserError("Vui lòng nhập Requisition Type")
            if rorder.requisition_type == 'purchase_order' and rorder.partner_id.id == False:
                raise UserError("Vui lòng nhập nhà cung cấp")
        """create purchase order and internal transfer"""
        move_ids_without_package1 = []
        move_ids_without_package2 = []
        created_id_po=[]
        order_line_arr = []
        
        # if not self.actual_deadline:
        #     raise UserError('Vui lòng nhập Actual Deadline trước khi tạo PO/Picking')
        
        for rec in self.requisition_order_ids:
            if rec.product_id.name == "Unknown":
                raise UserError('Không thể thực hiện thao tác này vì có sản phẩm Unknown trong phiếu. Vui lòng liên hệ Admin để được hỗ trợ')
            route = self.env['stock.route'].search([('name', 'in',['Manufacture','Sản xuất'])])   
            if rec.requisition_type == 'internal_transfer':
                if route.id in rec.product_id.product_tmpl_id.route_ids.ids:
                    move_ids_without_package1.append((0, 0,{
                        'name': rec.product_id.name,
                        'product_id': rec.product_id.id,
                        'product_uom': rec.product_id.uom_id,
                        'product_uom_qty': rec.quantity,
                        'location_id': self.source_location_id.id,
                        'location_dest_id': self.destination_location_id.id,
                    }))
                else:
                    move_ids_without_package2.append((0, 0,{
                        'name': rec.product_id.name,
                        'product_id': rec.product_id.id,
                        'product_uom': rec.product_id.uom_id,
                        'product_uom_qty': rec.quantity,
                        'location_id': self.source_location_id.id,
                        'location_dest_id': self.destination_location_id.id,
                    }))
                
            elif rec.requisition_type == 'purchase_order':
                if not rec.partner_id:
                    continue
                if rec.partner_id.id not in created_id_po:
                    order_line = []
                    for item in self.requisition_order_ids:
                        if not item.partner_id:
                            continue
                        if item.requisition_type == 'purchase_order':
                            if item.partner_id.id == rec.partner_id.id:
                                order_line.append((0, 0, {
                                    'product_id': item.product_id.id,
                                    'product_qty': item.quantity,
                                }))
                    order_line_arr.append({
                        'partner_id': rec.partner_id.id,
                        'order_line': order_line
                    })
                    created_id_po.append(rec.partner_id.id)
                
        if move_ids_without_package1:
            self.env['stock.picking'].create({
                'location_id': self.source_location_id.id,
                'location_dest_id': self.destination_location_id.id,
                'picking_type_id': self.internal_picking_id.id,
                'requisition_order': self.name,
                'move_ids_without_package': move_ids_without_package1
            })

        if move_ids_without_package2:
            self.env['stock.picking'].create({
                'location_id': self.source_location_id.id,
                'location_dest_id': self.destination_location_id.id,
                'picking_type_id': self.internal_picking_id.id,
                'requisition_order': self.name,
                'move_ids_without_package': move_ids_without_package2
            })
            
        if order_line_arr:
            API_KEY = 'yIj6dFf0J87QSr1RyKMIEBSBGvs58HdLg90UThEX0vVHMhdG5VK0cPuSQTVWdTaI'
            
            async def call_api_google_map(origin, destination):
                distance = 0
                try:
                    url = 'https://api-v2.distancematrix.ai/maps/api/distancematrix/'+'json?origins='+origin+'&destinations='+destination+'&key='+API_KEY
                    
                    response = requests.get(url=url)
                    if response.status_code == 200:
                        response = response.json()
                        if response['rows'][0]['elements'][0]['status'] == 'OK':
                            distance = response['rows'][0]['elements'][0]['distance']['value']
                except :
                    pass
                return distance
            
            def get_address_by_partner_id(partner_id):
                address = ""
                if partner_id.street and partner_id.street != '':
                    address += partner_id.street
                if partner_id.street2 and partner_id.street2 != '':
                    address += ", " + partner_id.street2
                if partner_id.city and partner_id.city != '':
                    address += ", " + partner_id.city
                if partner_id.country_id and partner_id.country_id != '':
                    address += ", " + partner_id.country_id.name
                return address
                    
            for i in order_line_arr:
                temp = self.env['purchase.order'].create({
                    #update 16/05/2023: 'partner_id': self.employee_id.work_contact_id.id,
                    'partner_id': i['partner_id'],
                    'requisition_order': self.name,
                    "order_line": i['order_line']
                })
                try:
                    if self.project_id and self.project_id.bkg_stock_info_id:
                        if self.x_requisitionsystem_id and self.x_requisitionsystem_id.x_name == 'Thiết bị chính':
                            temp.picking_type_id = self.project_id.bkg_stock_info_id.in_type_id
                        elif self.x_requisitionsystem_id:
                            partner_id = self.env['res.partner'].browse(i['partner_id'])
                            if partner_id:
                                vendor_address = get_address_by_partner_id(partner_id)
                                if vendor_address != "":
                                    min_distance = 0
                                    warehouse_id = None
                                    
                                    ## So với tất cả các kho
                                    warehouse_id = self.env['stock.warehouse'].search([('name', '=', 'Kho nhà máy'), ('code', '=', 'NM')])
                                    if len(warehouse_id) == 1:
                                        if warehouse_id.partner_id:
                                            ware_house_address = get_address_by_partner_id(warehouse_id.partner_id)
                                            if ware_house_address != '': 
                                                distance = asyncio.run(call_api_google_map(vendor_address, ware_house_address))
                                                if distance != 0:
                                                    min_distance = distance
                                                                
                                                    ## So với công trình
                                                    project_address = get_address_by_partner_id(self.project_id.bkg_stock_info_id.partner_id)
                                                    if project_address != "":
                                                        distance_2 = asyncio.run(call_api_google_map(vendor_address, project_address))
                                                        if distance_2 != 0:
                                                            ## Chuyển thẳng xuống công trình
                                                            if distance_2 < min_distance:
                                                                temp.picking_type_id = self.project_id.bkg_stock_info_id.in_type_id
                                                            ## Chuyển xuống kho
                                                            else:
                                                                ## Chuyển đích đến tới kho
                                                                if warehouse_id:
                                                                    temp.picking_type_id = warehouse_id.in_type_id
                                                                    
                                                                    ## Tạo 1 phiếu điều chuyển từ kho tới công trình
                                                                    move_ids_from_warehouse = []
                                                                    for temp_order in temp.order_line:
                                                                        move_ids_from_warehouse.append((0, 0, {
                                                                            'name': temp_order.product_id.name,
                                                                            'product_id': temp_order.product_id.id,
                                                                            'product_uom_qty': temp_order.product_qty,
                                                                            'location_id': warehouse_id.lot_stock_id.id,
                                                                            'location_dest_id': self.project_id.bkg_stock_info_id.lot_stock_id.id,
                                                                        }))
                                                                    self.env['stock.picking'].create({
                                                                        'location_id': warehouse_id.lot_stock_id.id,
                                                                        'location_dest_id': self.project_id.bkg_stock_info_id.lot_stock_id.id,
                                                                        'picking_type_id': warehouse_id.int_type_id.id,
                                                                        'requisition_order': self.name,
                                                                        'bkg_purchase_order_name': temp.name,
                                                                        'move_ids_without_package': move_ids_from_warehouse,
                                                                    })
                except:
                    pass
        
        self.write({'state': 'purchase_order_created'})
        self.purchase_count = self.env['purchase.order'].search_count([
            ('requisition_order', '=', self.name)])
        self.internal_transfer_count = self.env['stock.picking'].search_count([
            ('requisition_order', '=', self.name)])

    def action_receive(self):
        """receive purchase requisition"""
        self.write({'state': 'received'})
        self.receive_date = fields.Date.today()

    def get_purchase_order(self):
        """purchase order smart button view"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Order',
            'view_mode': 'tree,form',
            'res_model': 'purchase.order',
            'domain': [('requisition_order', '=', self.name)],
        }

    def get_internal_transfer(self):
        """internal transfer smart tab view"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Internal Transfers',
            'view_mode': 'tree,form',
            'res_model': 'stock.picking',
            'domain': [('requisition_order', '=', self.name)],
        }

    def action_print_report(self):
        """print purchase requisition report"""
        data = {
            'employee': self.employee_id.name,
            'records': self.read(),
            'order_ids': self.requisition_order_ids.read(),
        }
        print("a: ",self.env.ref(
            'employee_purchase_requisition.action_report_purchase_requisition'))
        return self.env.ref(
            'employee_purchase_requisition.action_report_purchase_requisition').report_action(
            self, data=data)

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = dict(default or {})
        default['confirmed_date'] = None
	#default['confirm_id'] = self.users.NULL
	#default['manager_id'] = None
	#default['department_approval_date'] = None
	#default['requisition_head_id'] = None
	#default['approval_date'] = None
	#default['rejected_user_id'] = None
	#default['reject_date'] = None
	#line_ids2 = []
	#default['order_line'] = line_ids2
        return super(PurchaseRequisition, self).copy(default=default)

    def import_ro(self):
        return {
            'name': 'Import',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'epr.importro',
            'target': 'new',
            'type': 'ir.actions.act_window',
            'context': {
                'epr_id': self.id,
            },
        }
         
    def write(self,vals): 
        if 'actual_deadline' in vals and vals['actual_deadline'] != False:
            if self.actual_deadline:
                vals['confirmed_by'] = self.env.user.id
                note = _(
                    'Confirmed Deadline is changed by %(user)s from %(date_from)s to %(date_to)s',
                    user=self.env.user.name,
                    date_from=self.actual_deadline,
                    date_to =vals['actual_deadline']
                )
                self.message_post(body=note)
            elif not self.actual_deadline:
                vals['confirmed_by'] = self.env.user.id
                note = _(
                    'Confirmed Deadline is created by %(user)s on %(date)s',
                    user=self.env.user.name,
                    date =vals['actual_deadline']
                )
                self.message_post(body=note)
        elif 'actual_deadline' in vals and vals['actual_deadline'] == False:
            if self.confirmed_by:
                vals['confirmed_by'] = None
                note = _(
                    'Confirmed Deadline is deleted by %(user)s',
                    user=self.env.user.name,
                )
                self.message_post(body=note)
                
        # if vals.get('requisition_order_ids') and (self.state == 'purchase_order_created' or self.state == 'received'):
        
        if vals.get('requisition_order_ids') and self.state in ['purchase_order_created', 'received']:
            try:
                bkg_check_update = False
                for order_id in vals.get('requisition_order_ids'):
                    ## 0: Add   1: Update   2: Unlink 
                    if order_id[0] == 0 or order_id[0] == 2:
                        bkg_check_update = True
                        break
                    elif order_id[0] == 1 and isinstance(order_id[2], dict):
                        temp_order = self.env['requisition.order'].browse(int(order_id[1]))
                        if order_id[2].get('quantity'):
                            if temp_order.quantity != float(order_id[2].get('quantity')):
                                bkg_check_update = True
                                break
                        if order_id[2].get('product_id'):
                            if temp_order.product_id.id != int(order_id[2].get('product_id')):
                                bkg_check_update = True
                                break
                        if order_id[2].get('partner_id'):
                            if temp_order.partner_id.id != int(order_id[2].get('partner_id')):
                                bkg_check_update = True
                                break
                        if order_id[2].get('requisition_type'):
                            if temp_order.requisition_type != order_id[2].get('requisition_type'):
                                bkg_check_update = True
                                break
            except:
                pass
                    
            if bkg_check_update: self.update({'state': 'approved'})
        res = super(PurchaseRequisition,self).write(vals)
        
        if 'project_task_id' in vals:
            if vals['project_task_id']:
                task = self.env['project.task'].browse(vals['project_task_id'])
                if task:
                    if not task.project_id:
                        stage_id = None
                        if self.project_id:
                            if not self.project_id.location_id or not self.project_id.location_dest_id or not self.project_id.picking_type_id:
                                raise UserError(
                                    ("Dự Án Hiện Tại Không có Đủ Nguồn Hàng.")
                                )
                            type = self.env['project.task.type'].search([('project_ids','in',self.project_id.id)])
                            if not type: 
                                raise UserError(
                                    ("Dự Án Hiện Tại Không có Tiến Trình Nào.")
                                )
                            else:
                                for t in type:
                                    if t.sequence == 0:
                                        stage_id = t.id
                                        break
                                if not stage_id:
                                    for t in type:
                                        if t.sequence == 1:
                                            stage_id = t.id
                                            break
                            if stage_id:
                                task.project_id = self.project_id.id
                                task.display_project_id = self.project_id.id
                                task.stage_id = stage_id
                                task.company_id = self.company_id.id
                                task.stock_analytic_account_id = self.project_id.id
                                distribution = {self.project_id.id: 100}
                                task.stock_analytic_distribution = distribution
                                ## Tao Stock Move Theo Requisition Order
                                ros = self.env['requisition.order'].search([('requisition_product_id','=', self.id)])
                                if ros:
                                    for ro in ros:
                                        move_new = {
                                            'sequence': 10,
                                            'company_id':task.project_id.company_id.id,
                                            'product_id': ro.product_id.id,
                                            'location_id': self.project_id.location_id.id,
                                            'location_dest_id': self.project_id.location_dest_id.id,
                                            'picking_type_id': self.project_id.picking_type_id.id,
                                            'product_uom_qty': ro.quantity,
                                            'description': ro.description,
                                            'raw_material_task_id': task.id,
                                            'name': task.name,
                                            'state': 'draft'
                                        }
                                        if task['group_id']:
                                            move_new['group_id'] = task['group_id']
                                        self.env['stock.move'].create(move_new)
        return res
    
    def test_email_bkg(self):
        b = self.env['mail.message'].search([('body', 'like', 'class="o_mail_redirect"'),('message_type', '=', 'comment'), ('email_add_signature', '=', True), ('subtype_id', '=', 1)])
        for temp in b :
            pass
        a = self.env['mail.message'].browse(96616)
        
    
    def check_edit_quantity_pr(self):
        for rorder in self.requisition_order_ids:
            if rorder.requisition_type in ['', None, False]:
                raise UserError("Vui lòng nhập Requisition Type")
            
        ##############################
        #### TRƯỜNG HỢP INTERNAL #####
        ##############################
        
        ### Tạo ARR dùng để chứa những sản phẩm
        current_pr_products_arr = []
        
        route = self.env['stock.route'].search([('name', 'in',['Manufacture','Sản xuất'])])   
        
        #### Những sản phẩm hiện tại trên pr ######
        for rorder in self.requisition_order_ids:
            if rorder.requisition_type == 'internal_transfer':
                check_arr_exist = False
                for current_products_item in current_pr_products_arr:
                    if current_products_item['product_id'] == rorder.product_id.id and current_products_item['product_uom'] == rorder.product_id.uom_id.id:
                        check_arr_exist = True
                        current_products_item['quantity'] += rorder.quantity
                if not check_arr_exist:
                    current_pr_products_arr.append({'name': rorder.product_id.name,'product_id': rorder.product_id.id, 'quantity': rorder.quantity, 'product_uom': rorder.product_id.uom_id.id, 'type': 1 if route.id in rorder.product_id.product_tmpl_id.route_ids.ids else 2})
                    
        #### Những sản phẩm hiện tại trên phiếu int #### 
        current_int_products_arr = []
        current_int_pickings = self.env['stock.picking'].search([('requisition_order', '=', self.name), ('bkg_purchase_order_name', 'in', [False, None, '']), ('state', '!=', 'cancel')])
        for picking in current_int_pickings:
            for move_id in picking.move_ids_without_package:
                check_arr_exist = False
                for current_int_products_item in current_int_products_arr:
                    if current_int_products_item['product_id'] == move_id.product_id.id and current_int_products_item['product_uom'] == move_id.product_uom.id:
                        check_arr_exist = True
                        ## Nếu origin = None: phiếu int != None: phiếu trả hàng
                        if picking.origin in [False, None, '']:
                            current_int_products_item['quantity'] += move_id.quantity_done
                        else:
                            current_int_products_item['quantity'] -= move_id.quantity_done
                if not check_arr_exist:
                    if picking.origin in [False, None,'']:
                        current_int_products_arr.append({'name': move_id.product_id.name,'product_id': move_id.product_id.id, 'quantity': move_id.quantity_done, 'product_uom': move_id.product_id.uom_id.id, 'type': 1 if route.id in move_id.product_id.product_tmpl_id.route_ids.ids else 2})
                    else:
                        current_int_products_arr.append({'name': move_id.product_id.name,'product_id': move_id.product_id.id, 'quantity': -move_id.quantity_done, 'product_uom': move_id.product_id.uom_id.id, 'type': 1 if route.id in move_id.product_id.product_tmpl_id.route_ids.ids else 2})

        ## Tạo arr
        edit_arr = []
        delete_arr = []
        create_arr = []
        
        ## Bắt đầu kiểm tra và chia ra 3 arr: create, delete và edit
        for current_pr_products_item in current_pr_products_arr:
            for current_int_products_item in current_int_products_arr:
                if current_pr_products_item['product_id'] == current_int_products_item['product_id'] and current_pr_products_item['product_uom'] == current_int_products_item['product_uom']:
                    check_edit = False
                    for edit_item in edit_arr:
                        if edit_item['product_id'] == current_int_products_item['product_id']:
                            check_edit = True
                            edit_item['quantity'] += current_pr_products_item['quantity'] - current_int_products_item['quantity']
                    if not check_edit:
                        edit_arr.append({'name': current_int_products_item['name'],'product_id': current_int_products_item['product_id'], 'quantity': current_pr_products_item['quantity'] - current_int_products_item['quantity'], 'product_uom': current_int_products_item['product_uom'], 'current_quantity': current_int_products_item['quantity'], 'type': current_int_products_item['type'] if current_int_products_item.get('type') else current_pr_products_item['type']})
        
        for edit_item in current_pr_products_arr:
            check_create = True
            for current_int_products_item in current_int_products_arr:
                if edit_item['product_id'] == current_int_products_item['product_id'] and edit_item['product_uom'] == current_int_products_item['product_uom']:
                    check_create = False
                    break
            if check_create:
                create_arr.append({'name': edit_item['name'],'product_id': edit_item['product_id'], 'quantity': edit_item['quantity'], 'product_uom': edit_item['product_uom'], 'type': edit_item.get('type'), 'current_quantity': 0})
        
        for current_int_products_item in current_int_products_arr:
            check_delete = True
            for edit_item in current_pr_products_arr:
                if edit_item['product_id'] == current_int_products_item['product_id'] and edit_item['product_uom'] == current_int_products_item['product_uom']:
                    check_delete = False
                    break
            if check_delete:
                delete_arr.append({'name': current_int_products_item['name'],'product_id': current_int_products_item['product_id'], 'quantity': current_int_products_item['quantity'], 'product_uom': current_int_products_item['product_uom'], 'type': current_int_products_item['type'] if current_int_products_item.get('type') else current_pr_products_item['type'], 'current_quantity': current_int_products_item['quantity']})
        
        ## Tạo arr cho việc sửa hoặc tạo phiếu mới
        return_arr = [] ## Arr trả hàng
        create_picking_arr = [] ## Tạo picking mới
        create_po_arr = [] ## Tạo PO mới
        edit_picking_arr = [] ## Sửa picking
        
        ## Kiểm tra return của internal transfer
        check_return_edit = False
        for edit_item in edit_arr:
            if edit_item['quantity'] < 0:
                for picking in self.env['stock.picking'].search([('requisition_order', '=', self.name), ('bkg_purchase_order_name', 'in', [False, None, '']), ('origin', 'in', [False, None, '']), ('state', '=', 'done')]):
                    for move_id in picking.move_ids_without_package:
                        if move_id.product_id.id == edit_item['product_id']:
                            check_returned = False
                            return_pickings = self.env['stock.picking'].search([('origin', 'in', ['Trả hàng ' + picking.name, 'Return of ' + picking.name]), ('state', '=', 'done')])
                            for return_picking in return_pickings:
                                for move_id_return in return_picking.move_ids_without_package:
                                    if move_id_return.product_id.id == move_id.product_id.id:
                                        check_returned = True
                                        break
                            if not check_returned: 
                                edit_item['return'] = True
                                return_arr = self.add_item_to_return_arr(picking, return_arr, move_id.product_id, False)
            elif edit_item['quantity'] == 0:
                del edit_item
         
        ## Kiểm tra delete arr 
        check_return_delete = False      
        for delete_item in delete_arr:
            if delete_item['quantity'] > 0:
                for picking in self.env['stock.picking'].search([('requisition_order', '=', self.name), ('bkg_purchase_order_name', 'in', [False, None, '']), ('origin', 'in', [False, None, '']), ('state', '=', 'done')]):
                    for move_id in picking.move_ids_without_package:
                        if move_id.product_id.id == delete_item['product_id']:
                            check_returned = False
                            return_pickings = self.env['stock.picking'].search([('origin', 'in', ['Trả hàng ' + picking.name, 'Return of ' + picking.name]), ('state', '=', 'done')])
                            for return_picking in return_pickings:
                                for move_id_return in return_picking.move_ids_without_package:
                                    if move_id_return.product_id.id == move_id.product_id.id:
                                        check_returned = True
                                        break
                            if not check_returned: 
                                check_return_delete = True
                                return_arr = self.add_item_to_return_arr(picking, return_arr, move_id.product_id, False)
            elif delete_item['quantity'] == 0:
                del delete_item
                
        current_int_pickings_not_done = self.env['stock.picking'].search([('requisition_order', '=', self.name), ('bkg_purchase_order_name', 'in', [False, None, '']), ('state', 'not in', ['done', 'cancel'])])
        check_edit_type_1 = False ## Loại 1: Sản xuất
        check_edit_type_2 = False ## Loại 2: Không sản xuất
        
        cancel_picking_type_1_arr = []
        cancel_picking_type_2_arr = []
        
        ## Lập delete ids arr để lọc những sản phẩm bị xoá
        delete_product_ids = []
        for delete_item in  delete_arr:
            if delete_item['product_id'] not in delete_product_ids: delete_product_ids.append(delete_item['product_id'])

        for picking in current_int_pickings_not_done:
            if len(picking.move_ids_without_package) > 0:
                if route.id in picking.move_ids_without_package[0].product_id.product_tmpl_id.route_ids.ids:
                    ## Loại 1:
                    if not check_edit_type_1:
                        if picking.move_ids_without_package[0].state == 'draft':
                            check_edit_type_1 = True
                            ## Trường hợp nháp -> unlink tất cả và bỏ tất cả sản phẩm cần sửa vào
                            move_ids_without_package = []
                            for edit_item in edit_arr:
                                if edit_item['type'] == 1 and edit_item['product_id'] not in delete_product_ids:
                                    if edit_item['quantity'] > 0:
                                        move_ids_without_package.append((0, 0, {
                                            'name': self.env['product.product'].browse(edit_item['product_id']).name,
                                            'product_id': edit_item['product_id'],
                                            'product_uom': edit_item['product_uom'],
                                            'product_uom_qty': edit_item['quantity'],
                                            'location_id': picking.location_id.id,
                                            'location_dest_id': picking.location_dest_id.id
                                        }))
                                    elif edit_item['quantity'] < 0:
                                        move_ids_without_package.append((0, 0, {
                                            'name': self.env['product.product'].browse(edit_item['product_id']).name,
                                            'product_id': edit_item['product_id'],
                                            'product_uom': edit_item['product_uom'],
                                            'product_uom_qty': edit_item['current_quantity'] + edit_item['quantity'],
                                            'location_id': picking.location_id.id,
                                            'location_dest_id': picking.location_dest_id.id
                                        }))
                            for create_item in create_arr:
                                if create_item['type'] == 1 and create_item['product_id'] not in delete_product_ids:
                                    move_ids_without_package.append((0, 0, {
                                        'name': self.env['product.product'].browse(create_item['product_id']).name,
                                        'product_id': create_item['product_id'],
                                        'product_uom': create_item['product_uom'],
                                        'product_uom_qty': create_item['quantity'],
                                        'location_id': picking.location_id.id,
                                        'location_dest_id': picking.location_dest_id.id
                                    }))
                            edit_picking_arr.append({'unlink': True, 'picking_id': picking.id, 'move_ids_without_package': move_ids_without_package})
                        else:
                            ## Từ trạng thái chờ trở đi : 1. Nếu có huỷ hoặc sửa: cancel và tạo phiếu mới 2. Chỉ thêm: Thêm vào phiếu hiện tại
                            check_edit_type_1 = True
                            check_cancel_picking = False
                            move_ids_without_package = []
                            for edit_item in edit_arr:
                                if edit_item['type'] == 1 and edit_item['product_id'] not in delete_product_ids:
                                    if edit_item['quantity'] > 0:
                                        check_cancel_picking = True
                                        move_ids_without_package.append((0, 0, {
                                            'name': self.env['product.product'].browse(edit_item['product_id']).name,
                                            'product_id': edit_item['product_id'],
                                            'product_uom': edit_item['product_uom'],
                                            'product_uom_qty': edit_item['quantity'],
                                            'location_id': picking.location_id.id,
                                            'location_dest_id': picking.location_dest_id.id
                                        }))
                                    elif edit_item['quantity'] < 0:
                                        check_cancel_picking = True
                                        move_ids_without_package.append((0, 0, {
                                            'name': self.env['product.product'].browse(edit_item['product_id']).name,
                                            'product_id': edit_item['product_id'],
                                            'product_uom': edit_item['product_uom'],
                                            'product_uom_qty': edit_item['current_quantity'] + edit_item['quantity'],
                                            'location_id': picking.location_id.id,
                                            'location_dest_id': picking.location_dest_id.id
                                        }))
                            ## Check xem picking có chứa sản phẩm xoá k, nếu có -> huỷ phiếu
                            for move_id in picking.move_ids_without_package:
                                for delete_item in delete_arr:
                                    if move_id.product_id.id == delete_item['product_id']:
                                        check_cancel_picking = True
                                        break
                            for create_item in create_arr:
                                if create_item['type'] == 1:
                                    move_ids_without_package.append((0, 0, {
                                        'name': self.env['product.product'].browse(create_item['product_id']).name,
                                        'product_id': create_item['product_id'],
                                        'product_uom': create_item['product_uom'],
                                        'product_uom_qty': create_item['quantity'],
                                        'location_id': picking.location_id.id,
                                        'location_dest_id': picking.location_dest_id.id
                                    }))
                            if check_cancel_picking:
                                cancel_picking_type_1_arr.append(picking.id)
                                if len(move_ids_without_package) > 0:
                                    create_picking_arr.append({
                                        'location_id': self.source_location_id.id,
                                        'location_dest_id': self.destination_location_id.id,
                                        'picking_type_id': self.internal_picking_id.id,
                                        'requisition_order': self.name,
                                        'move_ids_without_package': move_ids_without_package
                                    })
                            elif not check_cancel_picking:
                                edit_picking_arr.append({'unlink': False, 'picking_id': picking.id, 'move_ids_without_package': move_ids_without_package})
                else:
                    ## Loại 2:
                    if not check_edit_type_2:
                        if picking.move_ids_without_package[0].state == 'draft':
                            check_edit_type_2 = True
                            ## Trường hợp nháp -> unlink tất cả và bỏ tất cả sản phẩm cần sửa vào
                            move_ids_without_package = []
                            for edit_item in edit_arr:
                                if edit_item['type'] == 2 and edit_item['product_id'] not in delete_product_ids:
                                    if edit_item['quantity'] > 0:
                                        move_ids_without_package.append((0, 0, {
                                            'name': self.env['product.product'].browse(edit_item['product_id']).name,
                                            'product_id': edit_item['product_id'],
                                            'product_uom': edit_item['product_uom'],
                                            'product_uom_qty': edit_item['quantity'],
                                            'location_id': picking.location_id.id,
                                            'location_dest_id': picking.location_dest_id.id
                                        }))
                                    elif edit_item['quantity'] < 0:
                                        move_ids_without_package.append((0, 0, {
                                            'name': self.env['product.product'].browse(edit_item['product_id']).name,
                                            'product_id': edit_item['product_id'],
                                            'product_uom': edit_item['product_uom'],
                                            'product_uom_qty': edit_item['current_quantity'] + edit_item['quantity'],
                                            'location_id': picking.location_id.id,
                                            'location_dest_id': picking.location_dest_id.id
                                        }))
                            for create_item in create_arr:
                                if create_item['type'] == 2 and create_item['product_id'] not in delete_product_ids:
                                    move_ids_without_package.append((0, 0, {
                                        'name': self.env['product.product'].browse(create_item['product_id']).name,
                                        'product_id': create_item['product_id'],
                                        'product_uom': create_item['product_uom'],
                                        'product_uom_qty': create_item['quantity'],
                                        'location_id': picking.location_id.id,
                                        'location_dest_id': picking.location_dest_id.id
                                    }))
                            edit_picking_arr.append({'unlink': True, 'picking_id': picking.id, 'move_ids_without_package': move_ids_without_package})
                        else:
                            ## Từ trạng thái chờ trở đi : 1. Nếu có huỷ hoặc sửa: cancel và tạo phiếu mới 2. Chỉ thêm: Thêm vào phiếu hiện tại
                            check_edit_type_2 = True
                            check_cancel_picking = False
                            move_ids_without_package = []
                            for edit_item in edit_arr:
                                if edit_item['type'] == 2 and edit_item['product_id'] not in delete_product_ids:
                                    if edit_item['quantity'] > 0:
                                        check_cancel_picking = True
                                        move_ids_without_package.append((0, 0, {
                                            'name': self.env['product.product'].browse(edit_item['product_id']).name,
                                            'product_id': edit_item['product_id'],
                                            'product_uom': edit_item['product_uom'],
                                            'product_uom_qty': edit_item['quantity'],
                                            'location_id': picking.location_id.id,
                                            'location_dest_id': picking.location_dest_id.id
                                        }))
                                    elif edit_item['quantity'] < 0:
                                        check_cancel_picking = True
                                        move_ids_without_package.append((0, 0, {
                                            'name': self.env['product.product'].browse(edit_item['product_id']).name,
                                            'product_id': edit_item['product_id'],
                                            'product_uom': edit_item['product_uom'],
                                            'product_uom_qty': edit_item['current_quantity'] + edit_item['quantity'],
                                            'location_id': picking.location_id.id,
                                            'location_dest_id': picking.location_dest_id.id
                                        }))
                            ## Check xem picking có chứa sản phẩm xoá k, nếu có -> huỷ phiếu
                            for move_id in picking.move_ids_without_package:
                                for delete_item in delete_arr:
                                    if move_id.product_id.id == delete_item['product_id']:
                                        check_cancel_picking = True
                                        break
                            for create_item in create_arr:
                                if create_item['type'] == 2:
                                    move_ids_without_package.append((0, 0, {
                                        'name': self.env['product.product'].browse(create_item['product_id']).name,
                                        'product_id': create_item['product_id'],
                                        'product_uom': create_item['product_uom'],
                                        'product_uom_qty': create_item['quantity'],
                                        'location_id': picking.location_id.id,
                                        'location_dest_id': picking.location_dest_id.id
                                    }))
                            if check_cancel_picking:
                                cancel_picking_type_2_arr.append(picking.id)
                                if len(move_ids_without_package) > 0:
                                    create_picking_arr.append({
                                        'location_id': self.source_location_id.id,
                                        'location_dest_id': self.destination_location_id.id,
                                        'picking_type_id': self.internal_picking_id.id,
                                        'requisition_order': self.name,
                                        'move_ids_without_package': move_ids_without_package
                                    })
                            elif not check_cancel_picking:
                                edit_picking_arr.append({'unlink': False, 'picking_id': picking.id, 'move_ids_without_package': move_ids_without_package})
        ## Nếu không có bất kì phiếu nào có thể sửa -> tạo mới phiếu
        ## Type 1
        if not check_edit_type_1 and len(cancel_picking_type_1_arr) == 0:
            move_ids_without_package = []
            for edit_item in edit_arr:
                if edit_item['type'] == 1 and edit_item['product_id'] not in delete_product_ids:
                    if edit_item['quantity'] > 0:
                        move_ids_without_package.append((0, 0, {
                            'name': self.env['product.product'].browse(edit_item['product_id']).name,
                            'product_id': edit_item['product_id'],
                            'product_uom': edit_item['product_uom'],
                            'product_uom_qty': edit_item['quantity'],
                            'location_id': self.source_location_id.id,
                            'location_dest_id': self.destination_location_id.id
                        }))
                    elif edit_item['quantity'] < 0:
                        move_ids_without_package.append((0, 0, {
                            'name': self.env['product.product'].browse(edit_item['product_id']).name,
                            'product_id': edit_item['product_id'],
                            'product_uom': edit_item['product_uom'],
                            'product_uom_qty': edit_item['current_quantity'] + edit_item['quantity'],
                            'location_id': self.source_location_id.id,
                            'location_dest_id': self.destination_location_id.id
                        }))
            for create_item in create_arr:
                if create_item['type'] == 1:
                    move_ids_without_package.append((0, 0, {
                        'name': self.env['product.product'].browse(create_item['product_id']).name,
                        'product_id': create_item['product_id'],
                        'product_uom': create_item['product_uom'],
                        'product_uom_qty': create_item['quantity'],
                        'location_id': self.source_location_id.id,
                        'location_dest_id': self.destination_location_id.id
                    }))
            if len(move_ids_without_package) > 0:
                create_picking_arr.append({
                    'location_id': self.source_location_id.id,
                    'location_dest_id': self.destination_location_id.id,
                    'picking_type_id': self.internal_picking_id.id,
                    'requisition_order': self.name,
                    'move_ids_without_package': move_ids_without_package
                })
        ## Type 2
        if not check_edit_type_2 and len(cancel_picking_type_2_arr) == 0:
            move_ids_without_package = []
            for edit_item in edit_arr:
                if edit_item['type'] == 2 and edit_item['product_id'] not in delete_product_ids:
                    if edit_item['quantity'] > 0:
                        move_ids_without_package.append((0, 0, {
                            'name': self.env['product.product'].browse(edit_item['product_id']).name,
                            'product_id': edit_item['product_id'],
                            'product_uom': edit_item['product_uom'],
                            'product_uom_qty': edit_item['quantity'],
                            'location_id': self.source_location_id.id,
                            'location_dest_id': self.destination_location_id.id,
                        }))
                    elif edit_item['quantity'] < 0:
                        move_ids_without_package.append((0, 0, {
                            'name': self.env['product.product'].browse(edit_item['product_id']).name,
                            'product_id': edit_item['product_id'],
                            'product_uom': edit_item['product_uom'],
                            'product_uom_qty': edit_item['current_quantity'] + edit_item['quantity'],
                            'location_id': self.source_location_id.id,
                            'location_dest_id': self.destination_location_id.id
                        }))
            for create_item in create_arr:
                if create_item['type'] == 2:
                    move_ids_without_package.append((0, 0, {
                        'name': self.env['product.product'].browse(create_item['product_id']).name,
                        'product_id': create_item['product_id'],
                        'product_uom': create_item['product_uom'],
                        'product_uom_qty': create_item['quantity'],
                        'location_id': self.source_location_id.id,
                        'location_dest_id': self.destination_location_id.id
                    }))
            if len(move_ids_without_package) > 0:
                create_picking_arr.append({
                    'location_id': self.source_location_id.id,
                    'location_dest_id': self.destination_location_id.id,
                    'picking_type_id': self.internal_picking_id.id,
                    'requisition_order': self.name,
                    'move_ids_without_package': move_ids_without_package
                })
                
        #####################################
        #### TRƯỜNG HỢP PURCHASE ORDER ######
        #####################################

        current_pr_po_products_arr = []
        pr_partner_arr = []

        #### Những sản phẩm hiện tại trên pr ######
        for rorder in self.requisition_order_ids:
            if rorder.requisition_type == 'purchase_order':
                if not rorder.partner_id: raise UserError('Vui lòng nhập nhà cung cấp')
                if rorder.partner_id and rorder.partner_id.id not in pr_partner_arr: pr_partner_arr.append(rorder.partner_id.id)
                current_pr_po_products_arr.append({'product_id': rorder.product_id.id, 'quantity': rorder.quantity, 'product_uom': rorder.product_id.uom_id.id})
        
        for po_id in self.env['purchase.order'].search([('requisition_order', '=', self.name)]):
            if po_id.partner_id.id not in pr_partner_arr: pr_partner_arr.append(po_id.partner_id.id)
           
        ## Chứa những phiếu po cần cancel
        po_cancel_arr = []   
        ## Chứa arr update của order_line
        update_order_line_arr = []
        add_order_line_arr = []
        delete_order_line_arr = []
        picking_two_turn_cancel = []
         
        undo_pr_arr = [] 
        check_undo = False
            
        ## Gom lại theo partner
        for partner_id in pr_partner_arr:
            check_turn = False ## True: giao 2 lần, False: giao 1 lần
            check_po_exist = False ## True: đã tạo po(kiểm tra đc giao 1 lần hay 2 lần), False: chưa tạo bao giờ -> gọi api để tạo mới po
            target_po_id = None
            
            for po_id in self.env['purchase.order'].search([('requisition_order', '=', self.name), ('state', '!=', 'cancel')]):
                if po_id.partner_id.id == partner_id:
                    check_po_exist = True
                    target_po_id = po_id
                    if self.env['stock.picking'].search_count([('bkg_purchase_order_name', '=', po_id.name), ('state', '!=', 'cancel')]) > 0:
                        check_turn = True
                        break
                    break
            temp_pr_po_products_arr = []
                
            ## Tìm những sản phẩm po có partner giống trên pr
            for rorder in self.requisition_order_ids:
                if rorder.partner_id and rorder.partner_id.id == partner_id:
                    check_exist = False
                    for temp_pr_po_products_item in temp_pr_po_products_arr:
                        if temp_pr_po_products_item['product_id'] == rorder.product_id.id and temp_pr_po_products_item['product_uom'] == rorder.product_id.uom_id.id:
                            check_exist = True
                            temp_pr_po_products_item['quantity'] += rorder.quantity
                    if not check_exist:
                        temp_pr_po_products_arr.append({'name': rorder.product_id.name,'product_id': rorder.product_id.id, 'quantity': rorder.quantity, 'product_uom': rorder.product_id.uom_id.id})
            
            temp_create_po_arr = []
            temp_delete_po_arr = []
            ### Bắt đầu lọc nhưng sản phẩm cần thêm, xóa sửa
            if target_po_id:
                for temp_pr_po_products_item in temp_pr_po_products_arr:
                    check_create = True
                    for line in target_po_id.order_line:
                        if temp_pr_po_products_item['product_id'] == line.product_id.id:
                            check_create = False
                            break
                    if check_create:
                        temp_create_po_arr.append(temp_pr_po_products_item)
                for line in target_po_id.order_line:
                    check_delete = True
                    for temp_pr_po_products_item in temp_pr_po_products_arr:
                        if temp_pr_po_products_item['product_id'] == line.product_id.id:
                            check_delete = False
                            break
                    if check_delete:
                        temp_delete_po_arr.append({'product_id': line.product_id.id, 'line_id': line.id})
            
            ## Có po trùng
            if check_po_exist:
                
                ## Chia trường hợp
                ## 1. Nháp -> thêm xóa sửa vào nháp
                ## 2. waiting: -Nếu có xóa: Hủy phiếu và tạo phiếu po mới -Không có xóa: Thêm và sửa vào phiếu hiện tại
                if target_po_id.state in ['draft', 'sent', 'to approve']:
                    ## sửa
                    for line in target_po_id.order_line:
                        for edit_item in temp_pr_po_products_arr:
                            if line.product_id.id == edit_item['product_id'] and line.product_uom_qty != edit_item['quantity']:
                                check_exist = False
                                for order_line_item in update_order_line_arr:
                                    if order_line_item['line_id'] == line.id:
                                        check_exist = True
                                        order_line_item['quantity'] = edit_item['quantity']
                                        break
                                if not check_exist:
                                    update_order_line_arr.append({'line_id': line.id, 'quantity': edit_item['quantity']})
                    ## Thêm
                    for create_item in temp_create_po_arr:
                        check_exist = False
                        for add_item in add_order_line_arr:
                            if add_item['order_id'] == target_po_id.id and add_item['product_id'] == create_item['product_id']:
                                check_exist = True
                                add_item['quantity'] += create_item['quantity']
                        if not check_exist:
                            add_order_line_arr.append({'order_id': target_po_id.id, 'product_id': create_item['product_id'], 'quantity': create_item['quantity']})
                    ## Xóa
                    for delete_item in temp_delete_po_arr:
                        for line in target_po_id.order_line:
                            if delete_item['product_id'] == line.product_id.id:
                                check_exist = False
                                for delete_order_line_item in delete_order_line_arr:
                                    if delete_order_line_item['order_id'] == target_po_id.id and delete_order_line_item['line_id'] == line.id:
                                        check_exist = True
                                        break
                                if not check_exist:
                                    delete_order_line_arr.append({'order_id': target_po_id.id, 'line_id': line.id})
                    ## Check giao hàng lần 2
                    if check_turn:
                        temp_return_arr, temp_edit_picking_arr, temp_create_picking_arr, temp_cancel_picking_arr =self.deal_with_two_turn_purchase(new_po_name=None, return_arr=return_arr, po_id=target_po_id, create_picking_arr =[], edit_picking_arr=[], cancel_picking_arr=[], delete_arr=temp_delete_po_arr, edit_arr=temp_pr_po_products_arr, create_arr =temp_create_po_arr)
                        return_arr = temp_return_arr
                        for item in temp_edit_picking_arr:
                            edit_picking_arr.append(item)
                        for item in temp_create_picking_arr:
                            create_picking_arr.append(item)
                        for item in temp_cancel_picking_arr:
                            picking_two_turn_cancel.append(item)
                elif target_po_id.state in ['purchase', 'done']:
                    # if len(temp_delete_po_arr) > 0:
                    #     check_product_exist_state_done = False
                    #     for delete_item in temp_delete_po_arr:
                    #         for picking_id in target_po_id.picking_ids:
                    #             for move_id in picking_id.move_ids_without_package:
                    #                 if delete_item['product_id'] == move_id.product_id.id and move_id.state == 'done':
                    #                     check_product_exist_state_done = True
                    #                     break
                    #     if check_product_exist_state_done: 
                    #         check_undo = True
                    #         for temp_delete_po_item in temp_delete_po_arr:
                    #             undo_pr_arr.append(temp_delete_po_item)
                    if len(temp_delete_po_arr) > 0:
                        check_done_in_picking = False
                        for picking in target_po_id.picking_ids:
                            if picking.state == 'done':
                                check_done_in_picking = True
                        if check_done_in_picking:
                            check_undo = True
                            for temp_delete_po_item in temp_delete_po_arr:
                                undo_pr_arr.append(temp_delete_po_item)
                                
                    state_done = False
                    if target_po_id.state == 'done':
                        target_po_id.button_unlock()
                        state_done = True
                    
                    ## Nếu xóa -> hủy phiếu và tạo phiếu po mới
                    if len(temp_delete_po_arr) > 0:
                        delete_product_ids_arr = []
                        for temp_delete_po_item in temp_delete_po_arr:
                            if temp_delete_po_item['product_id'] not in delete_product_ids_arr: delete_product_ids_arr.append(temp_delete_po_item['product_id'])
                        ## Hủy phiếu và tạo phiếu mới
                        po_cancel_arr.append(target_po_id)
                        order_line = []
                        product_ids = []
                        for edit_item in temp_pr_po_products_arr:
                            if edit_item['product_id'] not in product_ids and edit_item['product_id'] not in delete_product_ids_arr:
                                product_ids.append(edit_item['product_id'])
                                order_line.append({
                                    'product_id': edit_item['product_id'],
                                    'product_qty': edit_item['quantity'],
                                })
                        for create_item in temp_create_po_arr:
                            if create_item['product_id'] not in product_ids and create_item['product_id'] not in delete_product_ids_arr:
                                product_ids.append(create_item['product_id'])
                                order_line.append({
                                    'product_id': create_item['product_id'],
                                    'product_qty': create_item['quantity'],
                                })
                        create_po_temp = {
                            'partner_id': target_po_id.partner_id.id,
                            'requisition_order': self.name,
                            "order_line": order_line,
                            'check_two_turn': False
                        }
                        ## Check giao hàng lần 2
                        if check_turn:
                            temp_return_arr, temp_edit_picking_arr, temp_create_picking_arr, temp_cancel_picking_arr =self.deal_with_two_turn_purchase(new_po_name=None, return_arr=return_arr, po_id=target_po_id, create_picking_arr =[], edit_picking_arr=[], cancel_picking_arr=[], delete_arr=temp_delete_po_arr, edit_arr=temp_pr_po_products_arr, create_arr =temp_create_po_arr)
                            return_arr = temp_return_arr
                            for item in temp_edit_picking_arr:
                                edit_picking_arr.append(item)
                            for item in temp_cancel_picking_arr:
                                picking_two_turn_cancel.append(item)
                            if len(temp_create_picking_arr) > 0:
                                create_po_temp['new_picking_two_turn'] = temp_create_picking_arr
                        create_po_temp['old_po_id'] = target_po_id.id
                        create_po_arr.append(create_po_temp)
                    ## Nếu sửa, thêm: 1. sửa ít hơn: trả hàng và cập nhật, sửa nhiều hơn: cập nhật
                    else:
                        complete_product_ids_arr = []
                        for line_id in target_po_id.order_line:
                            for edit_item in temp_pr_po_products_arr:  
                                if line_id.product_id.id == edit_item['product_id'] and line_id.product_id.id not in complete_product_ids_arr:
                                    complete_product_ids_arr.append(line_id.product_id.id)
                                    ## Nếu số lượng sửa > nhận: Sửa vào po
                                    if edit_item['quantity'] >= line_id.qty_received:
                                        for order_line_item in update_order_line_arr:
                                            if order_line_item['line_id'] == line_id.id:
                                                check_exist = True
                                                order_line_item['quantity'] = edit_item['quantity']
                                                break
                                        if not check_exist:
                                            update_order_line_arr.append({'line_id': line_id.id, 'quantity': edit_item['quantity']})
                                    ## Nếu số lượng sửa < nhận: trả hàng và sửa vào po 
                                    elif edit_item['quantity'] < line_id.qty_received:
                                        for picking in target_po_id.picking_ids:
                                            if picking.origin == target_po_id.name:
                                                for move_id in picking.move_ids_without_package:
                                                    if move_id.product_id.id == edit_item['product_id']:
                                                        return_arr = self.add_item_to_return_arr(picking, return_arr, move_id.product_id, True)
                                        update_order_line_arr.append({'line_id': line_id.id, 'quantity': edit_item['quantity']})
                        for create_item in temp_create_po_arr:
                            exist = False
                            for line_id_temp in target_po_id.order_line:
                                if line_id_temp.product_id.id == create_item['product_id']:
                                    exist = True
                                    break
                            if not exist:
                                check_exist = False
                                for add_item in add_order_line_arr:
                                    if add_item['order_id'] == target_po_id.id and add_item['product_id'] == create_item['product_id']:
                                        check_exist = True
                                        add_item['quantity'] += create_item['quantity']
                                if not check_exist:
                                    add_order_line_arr.append({'order_id': target_po_id.id, 'product_id': create_item['product_id'], 'quantity': create_item['quantity']})
                        ## Check giao hàng lần 2
                        if check_turn:
                            temp_return_arr, temp_edit_picking_arr, temp_create_picking_arr, temp_cancel_picking_arr =self.deal_with_two_turn_purchase(new_po_name=None, return_arr=return_arr, po_id=target_po_id, create_picking_arr =[], edit_picking_arr=[], cancel_picking_arr=[], delete_arr=temp_delete_po_arr, edit_arr=temp_pr_po_products_arr, create_arr =temp_create_po_arr)
                            return_arr = temp_return_arr
                            for item in temp_edit_picking_arr:
                                edit_picking_arr.append(item)
                            for item in temp_create_picking_arr:
                                create_picking_arr.append(item)
                            for item in temp_cancel_picking_arr:
                                picking_two_turn_cancel.append(item)
                    
                    
                # elif target_po_id.state in ['sent', 'purchase', 'to approve', 'done']:
                #     ## Kiểm tra nếu xóa sản phẩm trong phiếu picking đã done, purchase
                #     if len(temp_delete_po_arr) > 0:
                #         check_product_exist_state_done = False
                #         for delete_item in temp_delete_po_arr:
                #             for picking_id in target_po_id.picking_ids:
                #                 for move_id in picking_id.move_ids_without_package:
                #                     if delete_item['product_id'] == move_id.product_id.id and move_id.state == 'done':
                #                         check_product_exist_state_done = True
                #                         break
                #         if check_product_exist_state_done: 
                #             check_undo = True
                #             for temp_delete_po_item in temp_delete_po_arr:
                #                 undo_pr_arr.append(temp_delete_po_item)
                    
                #     state_done = False
                #     if target_po_id.state == 'done':
                #         target_po_id.button_unlock()
                #         state_done = True
                                
                #     if len(temp_delete_po_arr) == 0:
                #         ## sửa và thêm trên phiếu cũ
                #         ## Sửa
                #         for line in target_po_id.order_line:
                #             for edit_item in temp_pr_po_products_arr:
                #                 if line.product_id.id == edit_item['product_id'] and line.product_uom_qty != edit_item['quantity']:
                #                     check_exist = False
                #                     for order_line_item in update_order_line_arr:
                #                         if order_line_item['line_id'] == line.id:
                #                             check_exist = True
                #                             order_line_item['quantity'] = edit_item['quantity']
                #                             break
                #                     if not check_exist:
                #                         update_order_line_arr.append({'line_id': line.id, 'quantity': edit_item['quantity']})
                #         ## Thêm
                #         for create_item in temp_create_po_arr:
                #             check_exist = False
                #             for add_item in add_order_line_arr:
                #                 if add_item['order_id'] == target_po_id.id and add_item['product_id'] == create_item['product_id']:
                #                     check_exist = True
                #                     add_item['quantity'] += create_item['quantity']
                #             if not check_exist:
                #                 add_order_line_arr.append({'order_id': target_po_id.id, 'product_id': create_item['product_id'], 'quantity': create_item['quantity']})
                #         ## Check giao hàng lần 2
                #         if check_turn:
                #             temp_return_arr, temp_edit_picking_arr, temp_create_picking_arr, temp_cancel_picking_arr =self.deal_with_two_turn_purchase(new_po_name=None, return_arr=return_arr, po_id=target_po_id, create_picking_arr =[], edit_picking_arr=[], cancel_picking_arr=[], delete_arr=temp_delete_po_arr, edit_arr=temp_pr_po_products_arr, create_arr =temp_create_po_arr)
                #             return_arr = temp_return_arr
                #             for item in temp_edit_picking_arr:
                #                 edit_picking_arr.append(item)
                #             for item in temp_create_picking_arr:
                #                 create_picking_arr.append(item)
                #             for item in temp_cancel_picking_arr:
                #                 picking_two_turn_cancel.append(item)
                #     else:
                #         ## Hủy phiếu và tạo phiếu mới
                #         po_cancel_arr.append(target_po_id)
                #         order_line = []
                #         product_ids = []
                #         for edit_item in temp_pr_po_products_arr:
                #             if edit_item['product_id'] not in product_ids:
                #                 product_ids.append(edit_item['product_id'])
                #                 order_line.append({
                #                     'product_id': edit_item['product_id'],
                #                     'product_qty': edit_item['quantity'],
                #                 })
                #         for create_item in temp_create_po_arr:
                #             if edit_item['product_id'] not in product_ids:
                #                 product_ids.append(create_item['product_id'])
                #                 order_line.append({
                #                     'product_id': create_item['product_id'],
                #                     'product_qty': create_item['quantity'],
                #                 })
                #         # create_po_arr.append({
                #         #     'partner_id': target_po_id.partner_id.id,
                #         #     'requisition_order': self.name,
                #         #     "order_line": order_line,
                #         #     'check_two_turn': False
                #         # })
                #         create_po_temp = {
                #             'partner_id': target_po_id.partner_id.id,
                #             'requisition_order': self.name,
                #             "order_line": order_line,
                #             'check_two_turn': False
                #         }
                #         ## Check giao hàng lần 2
                #         if check_turn:
                #             temp_return_arr, temp_edit_picking_arr, temp_create_picking_arr, temp_cancel_picking_arr =self.deal_with_two_turn_purchase(new_po_name=None, return_arr=return_arr, po_id=target_po_id, create_picking_arr =[], edit_picking_arr=[], cancel_picking_arr=[], delete_arr=temp_delete_po_arr, edit_arr=temp_pr_po_products_arr, create_arr =temp_create_po_arr)
                #             return_arr = temp_return_arr
                #             for item in temp_edit_picking_arr:
                #                 edit_picking_arr.append(item)
                #             for item in temp_cancel_picking_arr:
                #                 picking_two_turn_cancel.append(item)
                #             if len(temp_create_picking_arr) > 0:
                #                 create_po_temp['new_picking_two_turn'] = temp_create_picking_arr
                #         create_po_temp['old_po_id'] = target_po_id.id
                #         create_po_arr.append(create_po_temp)
            
            
            elif not check_po_exist:
                order_line = []
                product_ids = []
                for edit_item in temp_pr_po_products_arr:
                    if edit_item['product_id'] not in product_ids:
                        product_ids.append(edit_item['product_id'])
                        order_line.append({
                            'product_id': edit_item['product_id'],
                            'product_qty': edit_item['quantity'],
                        })
                for create_item in temp_create_po_arr:
                    if create_item['product_id'] not in product_ids:
                        product_ids.append(create_item['product_id'])
                        order_line.append({
                            'product_id': create_item['product_id'],
                            'product_qty': create_item['quantity'],
                        })
                temp = {
                    'partner_id': partner_id,
                    'requisition_order': self.name,
                    "order_line": order_line
                }
                temp['check_two_turn'] = True
                create_po_arr.append(temp)
        if len(undo_pr_arr) > 0 or check_undo:
            requisition_order_ids = []
            for undo_item in undo_pr_arr:
                line_id = self.env['purchase.order.line'].browse(undo_item['line_id'])
                requisition_order_ids.append((0, 0, {
                    'requisition_type': 'purchase_order',
                    'product_id': line_id.product_id.id,
                    'quantity': line_id.product_qty,
                    'partner_id': line_id.order_id.partner_id.id
                }))
            self.update({
                'requisition_order_ids': requisition_order_ids
            })
                
            view = self.env.ref('employee_purchase_requisition.bkg_edit_pr_wizard')
            view_id = view and view.id or False
            context = dict(self._context or {})
            context['message'] = 'Không thể xóa sản phẩm khi phiếu nhập hoàn tất. Vui lòng liên hệ bộ phận IMS để được hỗ trợ'
            return{
                'name': 'Thông báo',
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_mode': 'form',
                'res_model': 'bkg.edit.pr.wizard',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'context': context
            }
                  
        # Gom hết những phiếu cần cancel lại 1 arr
        final_cancel_picking_arr = []   
        for cancel_picking_type_1_item in cancel_picking_type_1_arr:
            final_cancel_picking_arr.append(cancel_picking_type_1_item)
        for cancel_picking_type_2_item in cancel_picking_type_2_arr:
            final_cancel_picking_arr.append(cancel_picking_type_2_item)
        for picking_two_turn_cancel_item in picking_two_turn_cancel:
            final_cancel_picking_arr.append(picking_two_turn_cancel_item)
                            
        self.bkg_run_picking_and_po_dict(return_arr=return_arr, create_picking_arr=create_picking_arr, edit_picking_arr=edit_picking_arr, create_po_arr=create_po_arr, po_cancel_arr=po_cancel_arr, update_order_line_arr=update_order_line_arr, add_order_line_arr=add_order_line_arr, delete_order_line_arr=delete_order_line_arr, final_cancel_picking_arr=final_cancel_picking_arr)
    
    def bkg_run_picking_and_po_dict(self, return_arr = [], create_picking_arr=[], create_po_arr=[],edit_picking_arr=[], po_cancel_arr=[], update_order_line_arr=[], add_order_line_arr=[], delete_order_line_arr=[], final_cancel_picking_arr=[]):
        ## Trả hàng
        if len(return_arr) > 0:
            for return_item in return_arr:
                try:
                    if return_item.get('picking_id'):
                        temp = {
                            'picking_id': return_item.get('picking_id')
                        }
                        picking_id = self.env['stock.picking'].browse(return_item.get('picking_id'))
                        if return_item.get('location_dest_id'): temp['location_id'] = return_item.get('location_dest_id')
                        items = return_item.get('move_ids_without_package') if return_item.get('move_ids_without_package') else return_item.get('return_picking_lines')
                        line_arr = []
                        for item in return_item['items']:
                            check_exist = False
                            for move_id in picking_id.move_ids_without_package:
                                if item['product_id'] == move_id.product_id.id:
                                    check_exist = True
                                    break
                            if check_exist:
                                line_arr.append({
                                    'product_id': item['product_id'],
                                    'quantity': item['quantity'],
                                    'uom_id': item['uom_id'],
                                    'move_id': item['move_id']
                                })
                        if len(line_arr) > 0:
                            stock_return_picking_id = self.env['stock.return.picking'].create(temp)
                            stock_return_picking_id._onchange_picking_id()
                            stock_return_picking_id.product_return_moves.unlink()
                            
                            for line_item in line_arr:
                                self.env['stock.return.picking.line'].create({
                                    'product_id': line_item['product_id'],
                                    'quantity': line_item['quantity'],
                                    'uom_id': line_item['uom_id'],
                                    'wizard_id': stock_return_picking_id.id,
                                    'move_id': line_item['move_id']
                                })
                        
                            return_item_id = stock_return_picking_id.create_returns_bkg_inherit()
                            return_item_id = self.env['stock.picking'].browse(return_item_id)
                            return_item_id.bkg_purchase_order_name = None
                            return_item_id.date_done = fields.datetime.now()
                            for move_id in return_item_id.move_ids_without_package:
                                move_id.quantity_done = move_id.product_uom_qty
                            return_item_id.button_validate()
                            if not return_item.get('check_delete_requisition'):
                                return_item_id.requisition_order = self.name 
                except:
                    pass
        
        ## Update
        for item in update_order_line_arr:
            try:
                self.env['purchase.order.line'].browse(item['line_id']).update({'product_qty': item['quantity']})
            except:
                pass
        for item in add_order_line_arr:
            try:
                self.env['purchase.order'].browse(item['order_id']).update({
                    'order_line': [(0, 0, {
                        'product_id': item['product_id'],
                        'product_qty': item['quantity']
                    })]
                })
            except:
                pass
        for item in delete_order_line_arr:
            try:
                for line in self.env['purchase.order'].browse(item['order_id']).order_line:
                    if line.id == item['line_id']: 
                        line.unlink()
            except:
                pass  
        for item in edit_picking_arr:
            try:
                if item.get('unlink') and len(item.get('move_ids_without_package')) > 0:
                    picking_id = self.env['stock.picking'].browse(item['picking_id'])
                    picking_id.move_ids_without_package.unlink()
                    picking_id.update({
                        'move_ids_without_package': item['move_ids_without_package']
                    })
            except:
                pass
        
        ## Tạo phiếu PO và IT mới
        for item in create_picking_arr:
            try:
                if len(item['move_ids_without_package']) > 0 and item['requisition_order'] == self.name:
                    self.env['stock.picking'].create(item)
            except:
                pass
        for item in create_po_arr:
            try:
                if item.get('check_two_turn'):
                    ## Gọi API và xem tạo 1 hay 2 phiếu
                    new_po = self.env['purchase.order'].create({
                        'partner_id': item['partner_id'],
                        'requisition_order': item['requisition_order'],
                        'order_line': [(0, 0, {
                            'product_id': line['product_id'],
                            'product_qty': line['product_qty']
                        }) for line in item['order_line']]
                    })
                    
                    ## Hàm gọi API
                    API_KEY = 'yIj6dFf0J87QSr1RyKMIEBSBGvs58HdLg90UThEX0vVHMhdG5VK0cPuSQTVWdTaI'
            
                    async def call_api_google_map(origin, destination):
                        distance = 0
                        try:
                            url = 'https://api-v2.distancematrix.ai/maps/api/distancematrix/'+'json?origins='+origin+'&destinations='+destination+'&key='+API_KEY
                            
                            response = requests.get(url=url)
                            if response.status_code == 200:
                                response = response.json()
                                if response['rows'][0]['elements'][0]['status'] == 'OK':
                                    distance = response['rows'][0]['elements'][0]['distance']['value']
                        except :
                            pass
                        return distance
                    
                    def get_address_by_partner_id(partner_id):
                        address = ""
                        if partner_id.street and partner_id.street != '':
                            address += partner_id.street
                        if partner_id.street2 and partner_id.street2 != '':
                            address += ", " + partner_id.street2
                        if partner_id.city and partner_id.city != '':
                            address += ", " + partner_id.city
                        if partner_id.country_id and partner_id.country_id != '':
                            address += ", " + partner_id.country_id.name
                        return address
                    
                    try :
                        if self.project_id and self.project_id.bkg_stock_info_id:
                            if self.x_requisitionsystem_id and self.x_requisitionsystem_id.x_name == 'Thiết bị chính':
                                new_po.picking_type_id = self.project_id.bkg_stock_info_id.in_type_id
                            elif self.x_requisitionsystem_id:
                                origin_address = get_address_by_partner_id(new_po.partner_id)
                                warehouse_id = self.env['stock.warehouse'].search([('name', '=', 'Kho nhà máy'), ('code', '=', 'NM')])
                                if len(warehouse_id) == 1:
                                    ware_house_address = get_address_by_partner_id(warehouse_id.partner_id)
                                    if origin_address.strip() != '' or ware_house_address.strip() != '':
                                        warehouse_distance = asyncio.run(call_api_google_map(origin_address, ware_house_address))
                                        project_address = get_address_by_partner_id(self.project_id.bkg_stock_info_id.partner_id)
                                        if project_address.strip() != '':
                                            project_distance = asyncio.run(call_api_google_map(origin_address, project_address))
                                            if project_distance < warehouse_distance:
                                                new_po.picking_type_id = self.project_id.bkg_stock_info_id.in_type_id
                                            elif project_distance > warehouse_distance:
                                                ## Chuyển đích đến tới kho
                                                if warehouse_id:             
                                                    new_po.picking_type_id = warehouse_id.in_type_id   
                                                    ## Tạo 1 phiếu điều chuyển từ kho tới công trình
                                                    move_ids_from_warehouse = []
                                                    for temp_order in new_po.order_line:
                                                        move_ids_from_warehouse.append((0, 0, {
                                                            'name': temp_order.product_id.name,
                                                            'product_id': temp_order.product_id.id,
                                                            'product_uom_qty': temp_order.product_qty,
                                                            'location_id': warehouse_id.lot_stock_id.id,
                                                            'location_dest_id': self.project_id.bkg_stock_info_id.lot_stock_id.id,
                                                        }))
                                                    self.env['stock.picking'].create([{
                                                        'location_id': warehouse_id.lot_stock_id.id,
                                                        'location_dest_id': self.project_id.bkg_stock_info_id.lot_stock_id.id,
                                                        'picking_type_id': warehouse_id.int_type_id.id,
                                                        'requisition_order': self.name,
                                                        'bkg_purchase_order_name': new_po.name,
                                                        'move_ids_without_package': move_ids_from_warehouse,
                                                    }])
                    except:
                        pass
                else:
                    if len(item['order_line']) > 0:
                        new_po = self.env['purchase.order'].create({
                            'partner_id': item['partner_id'],
                            'requisition_order': item['requisition_order'],
                            'order_line': [(0, 0, {
                                'product_id': line['product_id'],
                                'product_qty': line['product_qty']
                            }) for line in item['order_line']]
                        })
                if item.get('new_picking_two_turn') and new_po:
                    for new_picking_two_turn_item in item.get('new_picking_two_turn'):
                        new_picking = self.env['stock.picking'].create(new_picking_two_turn_item)
                        new_picking.requisition_order = self.name
                        new_picking.bkg_purchase_order_name = new_po.name
                if new_po and item.get('old_po_id'):
                    try:
                        old_po_id = self.env['purchase.order'].browse(item.get('old_po_id'))
                        pickings = self.env['stock.picking'].search([('bkg_purchase_order_name', '=', old_po_id.name), ('origin', 'in', [None, False, ''])])
                        if len(pickings) > 0:
                            pickings[0].bkg_purchase_order_name = new_po.name
                    except:
                        pass
            except:
                pass
        
        ## Hủy phiếu PO và IT
        for item in po_cancel_arr:
            try:
                item.button_cancel()
            except:
                pass
        for item in final_cancel_picking_arr:
            try:
                # if item.get('')
                picking_cancel = self.env['stock.picking'].browse(item)
                picking_cancel.bkg_purchase_order_name = None
                if picking_cancel.state != 'done':
                    picking_cancel.action_cancel()
            except:
                pass
        self.purchase_count = self.env['purchase.order'].search_count([
            ('requisition_order', '=', self.name)])
        self.internal_transfer_count = self.env['stock.picking'].search_count([
            ('requisition_order', '=', self.name)])
        
        if self.state == 'approved':
            self.state = 'purchase_order_created'
        
            
    def deal_with_two_turn_purchase(self, new_po_name=None, return_arr=[], po_id=None, create_picking_arr =[], edit_picking_arr=[], cancel_picking_arr = [], delete_arr=[], edit_arr = [], create_arr = []):
        if po_id:
            two_turn_picking =  self.env['stock.picking'].search([('bkg_purchase_order_name', '=', po_id.name), ('state', '!=', 'cancel')])
            
            ## mảng kiểm tra id của product bị xóa
            delete_product_ids_arr = []
            for delete_item in delete_arr:
                if delete_item['product_id'] not in delete_product_ids_arr: delete_product_ids_arr.append(delete_item['product_id'])
                
            if len(two_turn_picking) == 1:
                ## Nháp -> sửa
                if two_turn_picking.state == 'draft':
                    move_ids_without_package = []
                    for edit_item in edit_arr:
                        if edit_item['product_id'] not in delete_product_ids_arr:
                            delete_product_ids_arr.append(edit_item['product_id'])
                            move_ids_without_package.append((0, 0, {
                                'name': self.env['product.product'].browse(edit_item['product_id']).name,
                                'product_id': edit_item['product_id'],
                                'product_uom': edit_item['product_uom'],
                                'product_uom_qty': edit_item['quantity'],
                                'location_id': two_turn_picking.location_id.id,
                                'location_dest_id': two_turn_picking.location_dest_id.id
                            }))
                    for create_item in create_arr:
                        if create_item['product_id'] not in delete_product_ids_arr:
                            delete_product_ids_arr.append(create_item['product_id'])
                            move_ids_without_package.append((0, 0, {
                                'name': self.env['product.product'].browse(create_item['product_id']).name,
                                'product_id': create_item['product_id'],
                                'product_uom': create_item['product_uom'],
                                'product_uom_qty': create_item['quantity'],
                                'location_id': two_turn_picking.location_id.id,
                                'location_dest_id': two_turn_picking.location_dest_id.id
                            }))
                    edit_picking_arr.append({'unlink': True, 'picking_id': two_turn_picking.id, 'move_ids_without_package': move_ids_without_package})
                ## Waiting, ready -> Sửa, xóa: hủy phiếu và tạo phiếu mới   Thêm: thêm vào phiếu hiện tại
                elif two_turn_picking.state in ['waiting', 'confirmed', 'assigned']:
                    if len(edit_arr) > 0 or len(delete_arr) > 0:
                        cancel_picking_arr.append(two_turn_picking.id)
                        move_ids_without_package = []
                        for edit_item in edit_arr:
                            if edit_item['product_id'] not in delete_product_ids_arr:
                                delete_product_ids_arr.append(edit_item['product_id'])
                                move_ids_without_package.append((0, 0, {
                                    'name': self.env['product.product'].browse(edit_item['product_id']).name,
                                    'product_id': edit_item['product_id'],
                                    'product_uom': edit_item['product_uom'],
                                    'product_uom_qty': edit_item['quantity'],
                                    'location_id': two_turn_picking.location_id.id,
                                    'location_dest_id': two_turn_picking.location_dest_id.id
                                }))
                        for create_item in create_arr:
                            if create_item['product_id'] not in delete_product_ids_arr:
                                delete_product_ids_arr.append(create_item['product_id'])
                                move_ids_without_package.append((0, 0, {
                                    'name': self.env['product.product'].browse(create_item['product_id']).name,
                                    'product_id': create_item['product_id'],
                                    'product_uom': create_item['product_uom'],
                                    'product_uom_qty': create_item['quantity'],
                                    'location_id': two_turn_picking.location_id.id,
                                    'location_dest_id': two_turn_picking.location_dest_id.id
                                }))
                        create_picking_arr.append({
                            'location_id': two_turn_picking.location_id.id,
                            'location_dest_id': two_turn_picking.location_dest_id.id,
                            'picking_type_id': two_turn_picking.picking_type_id.id,
                            'requisition_order': self.name,
                            'bkg_purchase_order_name': new_po_name if new_po_name else two_turn_picking.bkg_purchase_order_name,
                            'move_ids_without_package': move_ids_without_package
                        })
                        cancel_picking_arr.append(two_turn_picking.id)
                ## Done -> trả hàng và tạo phiếu mới
                elif two_turn_picking.state == 'done':
                    for move_id in two_turn_picking.move_ids_without_package:
                        return_arr = self.add_item_to_return_arr(two_turn_picking, return_arr, move_id.product_id, False)
                    move_ids_without_package = []
                    for edit_item in edit_arr:
                        if edit_item['product_id'] not in delete_product_ids_arr:
                            delete_product_ids_arr.append(edit_item['product_id'])
                            move_ids_without_package.append((0, 0, {
                                'name': self.env['product.product'].browse(edit_item['product_id']).name,
                                'product_id': edit_item['product_id'],
                                'product_uom': edit_item['product_uom'],
                                'product_uom_qty': edit_item['quantity'],
                                'location_id': two_turn_picking.location_id.id,
                                'location_dest_id': two_turn_picking.location_dest_id.id
                            }))
                    for create_item in create_arr:
                        if create_item['product_id'] not in delete_product_ids_arr:
                            delete_product_ids_arr.append(create_item['product_id'])
                            move_ids_without_package.append((0, 0, {
                                'name': self.env['product.product'].browse(create_item['product_id']).name,
                                'product_id': create_item['product_id'],
                                'product_uom': create_item['product_uom'],
                                'product_uom_qty': create_item['quantity'],
                                'location_id': two_turn_picking.location_id.id,
                                'location_dest_id': two_turn_picking.location_dest_id.id
                            }))
                    create_picking_arr.append({
                        'location_id': two_turn_picking.location_id.id,
                        'location_dest_id': two_turn_picking.location_dest_id.id,
                        'picking_type_id': two_turn_picking.picking_type_id.id,
                        'requisition_order': self.name,
                        'bkg_purchase_order_name': new_po_name if new_po_name else two_turn_picking.bkg_purchase_order_name,
                        'move_ids_without_package': move_ids_without_package
                    })
                    cancel_picking_arr.append(two_turn_picking.id)
        return return_arr, edit_picking_arr, create_picking_arr, cancel_picking_arr
    
    def add_item_to_return_arr(self, picking_id, return_arr, product_id, check_delete_requisition):  
        try:
            for move_id in picking_id.move_ids_without_package:
                if move_id.product_id.id == product_id.id:
                    exist_picking = False
                    for return_item in return_arr:
                        if picking_id.id == return_item['picking_id'] and return_item['check_delete_requisition'] == check_delete_requisition:
                            exist_picking = True
                            exist_item = False
                            for item in return_item['items']:
                                if item['product_id'] == product_id.id:
                                    exist_item = True
                                    break
                            if not exist_item:
                                return_item['items'].append({
                                    'product_id': product_id.id,
                                    'quantity': move_id.quantity_done,
                                    'uom_id': product_id.uom_id.id,
                                    'move_id': move_id.id
                                })
                    if not exist_picking:
                        return_arr.append({
                            'check_delete_requisition': check_delete_requisition,
                            'picking_id': picking_id.id,
                            'location_dest_id': picking_id.location_id.id,
                            'items': [{
                                'product_id': product_id.id,
                                'quantity': move_id.quantity_done,
                                'uom_id': product_id.uom_id.id,
                                'move_id': move_id.id
                            }]
                        })
        except:
            pass
        return  return_arr
        
    def export_pr(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('Sheet1')
        worksheet.set_zoom(100)
        
        worksheet.set_column("A:A", 30)
        worksheet.set_column("B:B", 30)
        worksheet.set_column("C:C", 30)
        worksheet.set_column("D:D", 30)
        worksheet.set_column("E:E", 30)
        worksheet.set_column("F:F", 30)
        worksheet.set_column("G:G", 30)
        worksheet.set_column("H:H", 30)
        worksheet.set_column("I:I", 30)
        worksheet.set_column("J:J", 30)
        worksheet.set_column("K:K", 30)
        
        ## INFO
        header = workbook.add_format()
        header.set_bold()
        header.set_align('left')
        header.set_align('vcenter')
        
        worksheet.write("A1","Department",header)
        worksheet.write("B1","Employee",header)
        worksheet.write("C1","Phân hệ",header)
        worksheet.write("D1","Reference No",header)
        worksheet.write("E1","Requisition Date",header)
        worksheet.write("F1","Requisition Responsible",header)
        worksheet.write("G1","State",header)
        worksheet.write("H1","Requisition Order/Product",header)
        worksheet.write("I1","Requisition Order/Quantity",header)
        worksheet.write("J1","Requisition Order/Unit of Measure",header)
        worksheet.write("K1","Requisition Order/Description",header)
        
        detail = workbook.add_format({'text_wrap': True})
        detail.set_align('left')
        detail.set_align('vcenter')
        
        index = 2
        
        for record in self:
            department_str = ""
            if record.employee_id and record.employee_id.department_id:
                department_str += str(record.employee_id.department_id.name)
            worksheet.write("A" + str(index),department_str,detail)
            worksheet.write("B" + str(index),str(record.employee_id.name),detail)
            requi_str = ""
            if record.x_requisitionsystem_id:
                requi_str += str(record.x_requisitionsystem_id.x_name)
            worksheet.write("C" + str(index),requi_str,detail)
            worksheet.write("D" + str(index),str(record.name),detail)
            
            date_str = ""
            if record.requisition_date:
                date_str += record.requisition_date.strftime('%Y-%m-%d')
            worksheet.write("E" + str(index),date_str,detail)
            worksheet.write("F" + str(index),str(record.user_id.name),detail)
            worksheet.write("G" + str(index),str(record.state),detail)
            
            requisition_order_ids = record.requisition_order_ids
            if requisition_order_ids:
                for requisition_order_id in requisition_order_ids:
                    worksheet.write("H" + str(index),str(requisition_order_id.product_id.display_name),detail)
                    worksheet.write("I" + str(index),str(requisition_order_id.quantity),detail)
                    worksheet.write("J" + str(index),str(requisition_order_id.uom),detail)
                    worksheet.write("K" + str(index),str(requisition_order_id.description),detail)
                    index += 1
            else: index += 1
        
        workbook.close()
        output.seek(0)

        self[0].export_pr_binary = base64.b64encode(output.read()).decode()
        self[0].export_pr_binary_name = "Purchase Requisition"
        file_url = "/web/content?model=employee.purchase.requisition&field=export_pr_binary&filename_field=export_pr_binary_name&id=" + str(self[0].id)
        return {
            'type': 'ir.actions.act_url',
            'url': file_url,
            'target': 'new'
        }  

class RequisitionProducts(models.Model):
    _name = 'x_requisition.system'
    
    x_name = fields.Text()

class RequisitionProducts(models.Model):
    _name = 'requisition.order'
    _description = 'Requisition order'
    _rec_name = 'product_id'
    _order = 'id asc'

    requisition_product_id = fields.Many2one(
        'employee.purchase.requisition', help='Requisition product.')
    state = fields.Selection(string='State',    
                             related='requisition_product_id.state')
    requisition_type = fields.Selection(
        string='Requisition Type',
        selection=[
            ('purchase_order', 'Purchase Order'),
            ('internal_transfer', 'Internal Transfer'),
        ], help='type of requisition')
    product_id = fields.Many2one('product.product', required=True,
                                 help='Product')
    description = fields.Text(
        string="Description",
        compute='_compute_name',
        store=True, readonly=False,
        precompute=True, help='Product Description')
    quantity = fields.Float(string='Quantity', help='Quantity', default=1)
    uom = fields.Char(related='product_id.uom_id.name',
                      string='Unit of Measure', help='Product Uom')
    partner_id = fields.Many2one('res.partner', string='Vendor',
                                 help='Vendor for the requisition')
    #Project stock
    project_task_id = fields.Many2one('project.task', string='Project Task ID', required=False, help='Requisition responsible user')
    stock_move_id = fields.Many2one('stock.move', string='Stock Move ID', required=False, help='Requisition responsible user')
    received_date = fields.Date(help='Requisition Approval Date')
    x_project_id = fields.Many2one('project.project')
    bkg_received_qty = fields.Float(string="Received", compute='_compute_bkg_received_qty')
    bkg_warning_qty_status = fields.Boolean(string="Status", compute='_compute_bkg_warning_qty_status')
    bkg_rorder_order = fields.Integer(string="No.", compute='_compute_bkg_rorder_order')
    
    @api.model
    def _compute_bkg_rorder_order(self):
        for record in self:
            epr_id = record.requisition_product_id
            bkg_rorder_order = 1
            for requisition_order_id in sorted(epr_id.requisition_order_ids, key=lambda roder: roder.id):
                if requisition_order_id.id != record.id:
                    bkg_rorder_order += 1
                    continue
                else:
                    break
            record.bkg_rorder_order = bkg_rorder_order
    
    @api.model
    def _compute_bkg_warning_qty_status(self):
        for record in self:
            status = False
            if record.requisition_product_id.actual_deadline:
                if (record.requisition_product_id.actual_deadline - fields.date.today()).days <= 2 and record.bkg_received_qty != record.quantity:
                    status = True
            record.bkg_warning_qty_status = status
            
    @api.model
    def _compute_bkg_received_qty(self):
        for record in self:
            bkg_received_qty = 0
            epr_id = record.requisition_product_id
            if record.requisition_type == 'internal_transfer':
                done_int_pickings = self.env['stock.picking'].search([('requisition_order', '=', epr_id.name), ('origin', 'in', [None, '']), ('bkg_purchase_order_name', 'in', [None, '']), ('state', '=', 'done')])
                for int_picking in done_int_pickings:
                    for move_id in int_picking.move_ids_without_package:
                        if record.product_id.id == move_id.product_id.id:
                            bkg_received_qty += move_id.quantity_done
                    return_pickings = self.env['stock.picking'].search(['|',('origin', '=', 'Trả hàng '+ int_picking.name), ('origin', '=', 'Return of '+ int_picking.name)])
                    for return_picking in return_pickings:
                        for move_id in return_picking.move_ids_without_package:
                            if record.product_id.id == move_id.product_id.id:
                                bkg_received_qty -= move_id.quantity_done
            elif record.requisition_type == 'purchase_order':
                po_ids = self.env['purchase.order'].search([('requisition_order', '=', epr_id.name)])
                for po_id in po_ids:
                    if record.partner_id:
                        if po_id.partner_id.id != record.partner_id.id:  continue
                        ## Check giao 1 lần hay 2 lần:
                        int_picking_2_turns_without_cancel = self.env['stock.picking'].search([('bkg_purchase_order_name', '=', po_id.name), ('state', '!=', 'cancel'), ('origin', 'in', [None, ''])])
                        # int_picking_2_turns_without_cancel = self.env['stock.picking'].search([('bkg_purchase_requisition', '=', po_id.name), ('state', '!=', 'cancel'), ('origin', 'in', [None, '']), ('location_dest_id', '=', epr_id.project_id.bkg_stock_info_id.lot_stock_id.id)])
                        if len(int_picking_2_turns_without_cancel) > 0:
                            ## Giao 2 lần
                            if epr_id.project_id and epr_id.project_id.bkg_stock_info_id:
                                done_int_picking_2_turns = self.env['stock.picking'].search([('bkg_purchase_order_name', '=', po_id.name), ('state', '=', 'done'), ('origin', 'in', [None, '']), ('location_dest_id', '=', epr_id.project_id.bkg_stock_info_id.lot_stock_id.id)])
                                for picking in done_int_picking_2_turns:
                                    if picking.state == 'done':
                                        for move_id in picking.move_ids_without_package:
                                            if record.product_id.id == move_id.product_id.id:
                                                bkg_received_qty += move_id.quantity_done
                        else:
                            ## Giao 1 lần
                            if po_id.state in ['done', 'purchase']:
                                for picking in po_id.picking_ids:
                                    if picking.state == 'done':
                                        for move_id in picking.move_ids_without_package:
                                            if record.product_id.id == move_id.product_id.id:
                                                if picking.origin == po_id.name:
                                                    bkg_received_qty += move_id.quantity_done
                                                elif picking.origin != None and picking.origin != '':
                                                    bkg_received_qty -= move_id.quantity_done
            for requisition_order_id in epr_id.requisition_order_ids:
                if requisition_order_id.id == record.id:
                    break
                if (requisition_order_id.id != record.id and requisition_order_id.product_id.id == record.product_id.id):
                    bkg_received_qty -= requisition_order_id.quantity
            if bkg_received_qty > record.quantity:
                bkg_received_qty = record.quantity
            elif bkg_received_qty < 0:
                bkg_received_qty = 0                              
            record.bkg_received_qty = bkg_received_qty
            # epr_id = record.requisition_product_id
            # requisition_order_ids = epr_id.requisition_order_ids
            # try:
            #     po_ids = record.env['purchase.order'].search([
            #     ('requisition_order', '=', epr_id.name)])
            #     epr_picking_ids = record.env['stock.picking'].search([
            #     ('requisition_order', '=', epr_id.name)])
            #     if epr_id.project_id and epr_id.project_id.bkg_stock_info_id:
            #         for po_id in po_ids:
            #             relate_pickings =  self.env['stock.picking'].search([('bkg_purchase_order_name', '=', po_id.name)])
            #             if len(relate_pickings) > 0:
            #                 for picking_id in relate_pickings:
            #                     if epr_id.project_id.bkg_stock_info_id.lot_stock_id.id == picking_id.location_dest_id.id and picking_id.state=='done':
            #                         for move_id_without_package in picking_id.move_ids_without_package:
            #                             if move_id_without_package.product_id.id == record.product_id.id:
            #                                 bkg_received_qty += move_id_without_package.quantity_done
            #             else:    
            #                 for picking_id in po_id.picking_ids:
            #                     if epr_id.project_id.bkg_stock_info_id.lot_stock_id.id == picking_id.location_dest_id.id and picking_id.state=='done':
            #                         for move_id_without_package in picking_id.move_ids_without_package:
            #                             if move_id_without_package.product_id.id == record.product_id.id:
            #                                 if picking_id.origin == po_id.name or picking_id.origin == False or picking_id.origin == '':
            #                                     bkg_received_qty += move_id_without_package.quantity_done
            #                                 else:
            #                                     bkg_received_qty -= move_id_without_package.quantity_done
            #                     elif picking_id.origin != po_id.name:
            #                         for move_id_without_package in picking_id.move_ids_without_package:
            #                             if move_id_without_package.product_id.id == record.product_id.id:
            #                                 bkg_received_qty -= move_id_without_package.quantity_done
            #         for picking_id in epr_picking_ids:
            #             if epr_id.project_id.bkg_stock_info_id.lot_stock_id.id == picking_id.location_dest_id.id and picking_id.state=='done':
            #                 for move_id_without_package in picking_id.move_ids_without_package:
            #                     if move_id_without_package.product_id.id == record.product_id.id:
            #                         if picking_id.origin == False or picking_id.origin == '':
            #                             bkg_received_qty += move_id_without_package.quantity_done
            #                         else:
            #                             bkg_received_qty -= move_id_without_package.quantity_done
            #             elif picking_id.origin != False and picking_id.origin != '':
            #                 for move_id_without_package in picking_id.move_ids_without_package:
            #                      if move_id_without_package.product_id.id == record.product_id.id:
            #                         bkg_received_qty -= move_id_without_package.quantity_done
                
            # except:
            #     pass
            # for requisition_order_id in requisition_order_ids:
            #     if requisition_order_id.id == record.id:
            #         break
            #     if (requisition_order_id.id != record.id and requisition_order_id.product_id.id == record.product_id.id):
            #         bkg_received_qty -= requisition_order_id.quantity
            # if bkg_received_qty > record.quantity:
            #     bkg_received_qty = record.quantity
            # elif bkg_received_qty < 0:
            #     bkg_received_qty = 0
            # record.bkg_received_qty = bkg_received_qty
                
                     
    @api.depends('product_id')
    def _compute_name(self):
        """compute product description"""
        for option in self:
            if not option.product_id:
                continue
            product_lang = option.product_id.with_context(
                lang=self.requisition_product_id.employee_id.lang)
            option.description = product_lang.get_product_multiline_description_sale()

    @api.onchange('requisition_type')
    def _onchange_product(self):
        """fetching product vendors"""
        vendors_list = []
        for data in self.product_id.seller_ids:
            vendors_list.append(data.partner_id.id)
        return {'domain': {'partner_id': [('id', 'in', vendors_list)]}}
    
        
 