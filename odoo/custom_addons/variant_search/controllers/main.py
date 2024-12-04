from odoo import http
from odoo.http import request

class ProductController(http.Controller):
    @http.route("/api/product/searchname/<string:var_desc>", type="json", auth="user", methods=["POST"], csrf=False)
    def search_product(self, var_desc, limit=100):
        Product = request.env['product.product']
        return Product.search_product_names(var_desc, limit)