"""
TODO
1. Add to Cart
2. GET user Cart
3. GET Shipping Price
4. Shipping
5. Create Order
"""
import sqlalchemy as sqlx

from flask import Blueprint, request, jsonify
from schema.meta import engine, meta
from sqlx import sqlx_gen_uuid, sqlx_easy_orm
from sqlx.base import DRow
from utils import get_time_epoch, run_query
from api.route.users import auth_with_token
import uuid


carts_bp = Blueprint("carts", __name__, url_prefix="/")

def get_shipping_prices(userdata: DRow):

    c = sqlx_easy_orm(engine, meta.tables.get("carts"))
    p = sqlx_easy_orm(engine, meta.tables.get("products"))

    j = sqlx.join(c.table, p.table, c.c.product_id == p.c.id)

    row = c.get(
        [
            sqlx.func.sum(p.c.price * c.c.quantity).label("total")
        ],
        [
            c.c.user_id
        ],
        j,
        user_id = userdata.id
    )

    if row is not None:

        total = row.total

        if isinstance(total, int):

            """
            regular

            < 200 15%

            >= 200 20%

            next day

            < 300 20%
            >= 300 25%
            """
            data = []

            ## flooring number

            ## regular
            regular = {
                "name": "regular",
                "price": int(total * .2 if 200 <= total else total * .15)
            }

            data += [regular]

            ## next day
            next_day = {
                "name": "next day",
                "price": int(total * .25 if 300 <= total else total * .2)
            }

            data += [next_day]

            return data, total

    return [], 0


@carts_bp.route("/cart", methods=["POST"])
def post_cart():
    auth = request.headers.get("authentication")
    
    def post_cart_main(userdata):
        body = request.json
        try:
            prd_id = body["id"]
        except:
            return jsonify({ "message": "error, item not valid" }), 400
        try:
            quantity = body["quantity"]
            if quantity < 1:
                return jsonify({ "message": "error, please specify the quantity" }), 400
        except:
            return jsonify({ "message": "error, quantity not valid" }), 400
        try:
            size = body["size"].upper()
            if size not in ['XS', 'S', 'M', 'L', 'XL', 'XXL']:
                return jsonify({ "message": "error, uncommon size" }), 400
        except:
            return jsonify({ "message": "error, size not valid" }), 400
        usr_id = userdata.id
        cart_id = uuid.uuid4()
        check_cart = run_query(f"SELECT * FROM carts WHERE user_id = '{usr_id}' AND product_id = '{prd_id}' AND size = '{size}'")
        if check_cart == []:
            run_query(f"INSERT INTO carts VALUES ('{cart_id}', '{usr_id}', '{prd_id}', {quantity}, '{size}', false)", True)
        else:
            run_query(f"UPDATE carts SET quantity = (quantity + {quantity}) WHERE user_id = '{usr_id}' AND product_id = '{prd_id}' AND size = '{size}'", True)
        return jsonify({ "message": "Item added to cart"}), 200
    
    return auth_with_token(auth, post_cart_main)


@carts_bp.route("/cart", methods=["GET"])
def get_cart():
    auth = request.headers.get("authentication")

    def get_cart_main(userdata):
        raw_data = run_query(f"SELECT id, quantity, size, product_id FROM carts WHERE user_id = '{userdata.id}' AND is_ordered != 'true'")
        data = []
        for item in raw_data:
            product_id = item["product_id"]
            prd_dtl = run_query(f"SELECT products.price, products.name, products.images FROM products JOIN categories ON products.category_id = categories.id WHERE products.is_deleted != 'true' AND categories.is_deleted != 'true' AND products.id = '{product_id}'")
            req = {
                "id": item["id"],
                "details": {
                    "quantity": item["quantity"],
                    "size": item["size"]
                },
                "price": prd_dtl[0]["price"],
                "image": prd_dtl[0]["images"],
                "name": prd_dtl[0]["name"]
            }
            data.append(req)
        return data, 200

    return auth_with_token(auth, get_cart_main)


@carts_bp.route("/cart/<string:cart_id>", methods=["DELETE"])
def delete_cart(cart_id):
    auth = request.headers.get("authentication")
    
    def delete_cart_main(userdata):
        uid = run_query(f"SELECT user_id FROM carts WHERE id = '{cart_id}'")
        if uid != []:
            if userdata.id == uid[0]["user_id"]:
                try:
                    run_query(f"DELETE FROM carts WHERE id = '{cart_id}'", True)
                except:
                    return jsonify({ "message": "error, item not valid"}), 400
                return jsonify({ "message": "Cart deleted"}), 200
            else:
                return jsonify({ "message": "error, user unauthorized"}), 400
        else:
            jsonify({ "message": "error, item not found"}), 400

    return auth_with_token(auth, delete_cart_main)


@carts_bp.route("/shipping_price", methods=["GET"])
def shipping_price_page():

    auth = request.headers.get("authentication")

    def shipping_price_page_main(userdata):

        data, _ = get_shipping_prices(userdata)

        if len(data) > 0:

            return jsonify({ "message": "success, shipping_price found", "data": data }), 200

        return jsonify({ "message": "error, tidak bisa mengambil metode harga"}), 400

    return auth_with_token(auth, shipping_price_page_main)

@carts_bp.route("/order", methods=["POST"])
def order_page():

    auth = request.headers.get("authentication")
    shipping_method = request.json.get("shipping_method")
    shipping_address = request.json.get("shipping_address")

    def order_page_main(userdata):

        """
        shipping_method
        “Same day”
        
        shipping_address
        {
            "name": "address name",
            "phone_number": "082713626",
            "address" : "22, ciracas, east jakarta",
            "city": "Jakarta
        }
        """
        if shipping_method is not None:
            if shipping_address is not None:
        
                shipping_prices, total = get_shipping_prices(userdata)

                shipping_price_info = None

                for shipping_price in shipping_prices:

                    if shipping_price["name"] == shipping_method.lower():

                        shipping_price_info = shipping_price
                        break

                if shipping_price_info is not None:

                    name = shipping_address["name"] if "name" in shipping_address else None
                    phone_number = shipping_address["phone_number"] if "phone_number" in shipping_address else None
                    address = shipping_address["address"] if "address" in shipping_address else None
                    city = shipping_address["city"] if "city" in shipping_address else None

                    if name is None:

                        return jsonify({ "message": "error, shipping_address.name not found" }), 400

                    if phone_number is None:

                        return jsonify({ "message": "error, shipping_address.phone_number not found" }), 400

                    if address is None:

                        return jsonify({ "message": "error, shipping_address.address not found" }), 400

                    if city is None:

                        return jsonify({ "message": "error, shipping_address.city not found" }), 400

                    ## -- useless --
                    ## name
                    ## phone_number
                    ## address
                    ## city

                    cost = total + shipping_price_info["price"]

                    o = sqlx_easy_orm(engine, meta.tables.get("orders"))
                    u = sqlx_easy_orm(engine, meta.tables.get("users"))
                    
                    if o.post(sqlx_gen_uuid(), userdata.id, shipping_method, "waiting", get_time_epoch()):

                        buyer = u.get(userdata.id, balance=0)
                        if buyer.balance < cost:

                            return jsonify({ "message": "error, user balance not enough" }), 400  

                        ## DEBUG
                        ## DEBUG
                        ## DEBUG

                        if u.update(buyer.id, balance=buyer.balance - cost):

                            seller = u.get(type=True)

                            if u.update(seller.id, balance=seller.balance + cost):

                                return jsonify({ "message": "Order success" }), 200

                        return jsonify({ "message": "error, order cannot process" }), 500

        return jsonify({ "message": "error, order failed" }), 400

    return auth_with_token(auth, order_page_main)