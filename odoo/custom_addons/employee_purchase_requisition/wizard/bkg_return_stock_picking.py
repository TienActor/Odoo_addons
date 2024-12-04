from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

# class BKGReturnModal(models.TransientModel):
#     """ Model for storing purchase requisition """
#     _name = 'bkg.return.modal'
    
#     bkg_return_stock_picking_ids = fields.One2many('bkg.return.stock.picking', 'bkg_return_stock_picking_id')
#     bkg_new_stock_picking_ids = fields.One2many('bkg.new.stock.picking', 'bkg_return_stock_picking_id')
#     bkg_update_order_line_ids = fields.One2many('bkg.update.order.line', 'bkg_return_stock_picking_id')
#     bkg_update_stock_move_ids = fields.One2many('bkg.update.stock.move', 'bkg_return_stock_picking_id')
    
# class BKGReturnStockPicking(models.TransientModel):
#     _name = 'bkg.return.stock.picking'
    
#     bkg_return_stock_picking_id = fields.Many2one('bkg.return.stock.picking', required=True)
#     location_id = fields.Many2one('stock.location', required=True)
#     location_dest_id = fields.Float('stock.location', required=True)
#     picking_type_id = fields.Many2one('stock.picking.type', required=True)
#     requisition_order = fields.Char()
#     move_ids_without_package = fields.One2many('bkg.return.stock.picking.line')
    
# class BKGReturnStockPickingLine(models.TransientModel):   
#     _name = 'bkg.return.stock.picking.line'
    
#     name = fields.Char()
#     product_id = fields.Many2one('product.product', required=True)
#     product_uom = fields.Many2one(related="product_id.uom_id")
#     product_uom_qty = fields.Float(default=1, required=True)
#     location_id = fields.Many2one('stock.location', required=True)
#     location_dest_id = fields.Many2one('stock.location', required=True)

# class BKGNewStockPicking(models.TransientModel): 
#     _name = 'bkg.new.stock.picking'

class BKGReturnModal(models.TransientModel):
    """ Model for storing purchase requisition """
    _name = 'bkg.return.modal'
    
    def create_returns(self):
        context = self.env.context.get('edit_data')
        pass