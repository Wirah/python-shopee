import os
import time
import json
import hmac, hashlib
from requests import Request, Session, exceptions
from .shop import Shop
from .shopcategory import ShopCategory
from .item import Item
from .image import Image
from .discount import Discount
from .order import Order
from .logistic import Logistic
from .rma import RMA


# installed sub-module
registered_module = {
    "shop":Shop,
    "shopcategory": ShopCategory,
    "item": Item,
    "image":Image,
    "discount":Discount,
    "order": Order,
    "logistic": Logistic,
    "rma": RMA,
}


class ClientMeta(type):
    def __new__(mcs, name, bases, dct):
        klass = super(ClientMeta, mcs).__new__(mcs, name, bases, dct)
        setattr( klass, "registered_module", registered_module )
        return klass


class Client(object, metaclass=ClientMeta):
    __metaclass__ = ClientMeta

    CACHED_MODULE = {}
    
    BASE_URL = "https://partner.shopeemobile.com/api/v1"
    # PER_MINUTE_API_RATE = 1000

    def __init__(self, shop_id, partner_id, secret_key):
        self.shop_id = shop_id
        self.partner_id = partner_id
        self.secret_key = secret_key

    def __getattr__(self, name):
        try:
            value = super(Client, self).__getattribute__(name)
        except AttributeError as e:
            value = self._get_cached_module(name)
            if not value:
                raise e
        return value

    def _make_timestamp(self):
        return int(time.time())

    def _make_default_parameter(self):
        return {
            "partner_id": self.partner_id,
            "shopid": self.shop_id,
            "timestamp": self._make_timestamp()
        }

    def _sign(self, url, body):
        bs = url + "|" + json.dumps(body)
        dig = hmac.new(self.secret_key.encode(), msg=bs.encode(), digestmod=hashlib.sha256).hexdigest()
        return dig

    def _build_request(self, uri, method, body):
        method = method.upper()
        url = self.BASE_URL + "/" + uri
        authorization = self._sign(url, body)
        
        headers = {
            "Authorization":authorization
        }
        
        req = Request(method, url, headers=headers)

        if body:
            if req.method in ["POST", "PUT", "PATH"]:
                req.json = body
            else:
                req.params = body
        return req

    def _build_response(self, resp):

        body = json.loads(resp.text)
        if "error" not in body:
            return body
        else:
            raise AttributeError(body["error"])

    def _get_cached_module(self, key):
        CACHED_MODULE = self.CACHED_MODULE.get(key)

        if not CACHED_MODULE:
            installed = self.registered_module.get(key)
            if not installed:
                return None
            CACHED_MODULE = installed(self)
            self.CACHED_MODULE.setdefault(key, CACHED_MODULE)
        return CACHED_MODULE


    def execute(self, uri, method, body=None):
        parameter = self._make_default_parameter()

        if body is not None:
            parameter.update(body)

        req = self._build_request(uri, method, parameter)
        prepped = req.prepare()
        
        s = Session()
        resp = s.send(prepped)
        resp = self._build_response(resp)
        return resp


    def shop_authorization(self, uri, method, redirect_url):
        '''
            The difference between hmac and hashlib, 
            hmac uses the provided key to generate a salt and make the hash more strong, while hashlib only hashes the provided message

            In shopee partner API, shopee use hmac for general encryption while using hashlib for Authorize and CancelAuthorize module
        '''
        bs = self.secret_key + redirect_url
        dig = hashlib.sha256(bs.encode()).hexdigest()
        
        parameters = "/{0}?id={1}&token={2}&redirect={3}".format(uri,self.partner_id,dig,redirect_url)
        uri = self.BASE_URL + parameters
        return uri
