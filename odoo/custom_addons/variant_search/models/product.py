# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools
from odoo.addons import product
from odoo import http
from odoo.http import route, request
import json
import re
import logging
_logger = logging.getLogger(__name__)

class ProductTemplateAttributeValue(models.Model):
	"""
	This is a bugfix to Odoo 10.0
	Categories should not be ordered alphabetically.
	Categories should be ordered according to their choosen order (i.e. sequence field).
	"""
	_inherit = 'product.template.attribute.value'

	def _variant_name(self, variable_attributes):
		return ", ".join([v.name for v in self.sorted(key=lambda r: r.attribute_id.sequence) if v.attribute_id in variable_attributes])



class ProductProductExt(models.Model):
	"""
	When the variants are saved, we store the whole description in "var_desc" field.
	When searching for products, e.g. in invoice line, we perform search in that field.
	Moreover, during this search we convert ' '  to '%' (this could be useful in standard search, too).
	WARNING: we lose the "customer" description.
	"""
	_inherit = 'product.product'
	var_desc = fields.Char(comment='Variant description', compute='_compute_var_desc', store=True)
	#var_desc = fields.Char(comment='Variant description', store=True)

	
	def name_get(self):
		def _name_get(d):
			name = d.get('name', '')
			code = self._context.get('display_default_code', True) and d.get('default_code', False) or False
			if code:
				name = '[%s] %s' % (code,name)
			return (d['id'], name)

		partner_id = self._context.get('partner_id')
		if partner_id:
			partner_ids = [partner_id, self.env['res.partner'].browse(partner_id).commercial_partner_id.id]
		else:
			partner_ids = []

		# all user don't have access to seller and partner
		# check access and use superuser
		self.check_access_rights("read")
		self.check_access_rule("read")

		result = []
		for product in self.sudo():
			# display all the attributes 
			variable_attributes = product.attribute_line_ids.mapped('attribute_id')
			variant = product.product_template_attribute_value_ids._variant_name(variable_attributes)

			name = variant and "%s (%s)" % (product.name, variant) or product.name
			sellers = []
			if partner_ids:
				sellers = [x for x in product.seller_ids if (x.partner_id.id in partner_ids) and (x.product_id == product)]
				if not sellers:
					sellers = [x for x in product.seller_ids if (x.partner_id.id in partner_ids) and not x.product_id]
			if sellers:
				for s in sellers:
					seller_variant = s.product_name and (
						variant and "%s (%s)" % (s.product_name, variant) or s.product_name
						) or False
					mydict = {
							  'id': product.id,
							  'name': seller_variant or name,
							  'default_code': s.product_code or product.default_code,
							  }
					temp = _name_get(mydict)
					if temp not in result:
						result.append(temp)
			else:
				mydict = {
						  'id': product.id,
						  'name': name,
						  'default_code': product.default_code,
						  }
				result.append(_name_get(mydict))
		return result

					
	@api.model
	def name_search(self, name='', args=None, operator='ilike', limit=None):
		if not name or args is None:
			return super(ProductProductExt, self).name_search(name=name, args=args, operator=operator, limit=80)

		pieces = name.lower().split()
		
		# Sử dụng SQL để lọc và lấy tất cả thông tin cần thiết trong một truy vấn
		query = """
		SELECT pp.id, pt.name, pp.var_desc, pp.default_code
		FROM product_product pp
		JOIN product_template pt ON pp.product_tmpl_id = pt.id
		WHERE (CAST(pp.var_desc AS text) ILIKE %s OR CAST(pt.name AS text) ILIKE %s)
		"""
		param = '%' + '%'.join(pieces) + '%'
		self.env.cr.execute(query, (param, param))
		results = self.env.cr.fetchall()

		def get_name_string(name):
			if isinstance(name, dict):
				return name.get(self.env.lang) or name.get('en_US') or next(iter(name.values()))
			return name or ''

		def calculate_score(name, var_desc):
			name_lower = get_name_string(name).lower()
			desc_lower = (var_desc or '').lower()
			name_part, _, attr_part = desc_lower.partition('(')
			name_part = name_part.strip()
			attr_part = attr_part.rstrip(')').strip()

			# Ưu tiên cho sản phẩm không có biến thể
			no_variant = 20 if name_part == desc_lower else 0

			# Ưu tiên cho sản phẩm có tên khớp chính xác với từ khóa tìm kiếm
			exact_name_score = 10 if name_lower == pieces[0] else 0

			# Sự xuất hiện của từ khóa trong tên sản phẩm
			name_score = sum(1 for p in pieces if p in name_lower)

			# Vị trí xuất hiện của từ khóa trong tên sản phẩm
			position_score = 2 if name_lower.startswith(pieces[0]) else 0

			return no_variant + exact_name_score + name_score + position_score

		scored_results = [(id, name, var_desc, default_code, calculate_score(name, var_desc)) 
                          for id, name, var_desc, default_code in results]
		# Sắp xếp theo điểm số giảm dần
		sorted_results = sorted(scored_results, key=lambda x: (-x[4], get_name_string(x[1]).lower()))  
        
		# Lọc kết quả có điểm số dương
		valid_results = [r for r in sorted_results if r[4] > 0]

		# Nhóm kết quả theo tên sản phẩm
		grouped_results = {}
		for r in valid_results:
			key = get_name_string(r[1]).lower()
			if key not in grouped_results:
				grouped_results[key] = []
			grouped_results[key].append(r)

		final_results = []
		for key in sorted(grouped_results.keys(), key=lambda k: -max(r[4] for r in grouped_results[k])):
			final_results.extend(grouped_results[key])


		# Tạo kết quả name_get trực tiếp từ final_results
		name_get_results = []
		for id, name, var_desc, default_code, score in final_results:
			display_name = get_name_string(name)
			
			# Kiểm tra xem var_desc có chứa thông tin biến thể không
			if var_desc and var_desc != display_name:
				# Tách phần tên và phần thuộc tính
				base_name, _, attributes = var_desc.partition('(')
				base_name = base_name.strip()
				attributes = attributes.rstrip(')').strip()
				
				# Nếu phần tên trong var_desc khác với display_name, sử dụng var_desc
				if base_name != display_name:
					display_name = var_desc
				# Ngược lại, chỉ thêm phần thuộc tính
				elif attributes:
					display_name = f"{display_name} ({attributes})"
			
			if default_code:
				display_name = f"[{default_code}] {display_name}"
			
			name_get_results.append((id, display_name))

		# Trả về tất cả kết quả mà không giới hạn
		return name_get_results
	
	@api.depends('product_template_attribute_value_ids', 'name')
	def _compute_var_desc(self):
		for rec in self:
			# Lấy tên biến thể dựa trên các giá trị thuộc tính của sản phẩm.	
			attributes = rec.product_template_attribute_value_ids._variant_name(rec.attribute_line_ids.mapped('attribute_id'))
			rec.var_desc = f"{rec.name} ({attributes})" if attributes else rec.name