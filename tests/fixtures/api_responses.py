"""
Mock API 响应数据

用于测试各 API 的成功、失败、异常场景
"""

# 高德地图 API 响应
AMAP_SUCCESS_RESPONSE = {
    "status": "1",
    "info": "OK",
    "geocodes": [{
        "formatted_address": "北京市朝阳区建国路88号",
        "location": "116.4699,39.9059",
        "province": "北京市",
        "city": "朝阳区",
        "district": "",
        "level": "地址"
    }]
}

AMAP_SUCCESS_RESPONSE_SIMPLE = {
    "status": "1",
    "info": "OK",
    "geocodes": [{
        "formatted_address": "北京市朝阳区",
        "location": "116.4853,39.9289",
        "province": "北京市",
        "city": "朝阳区",
        "district": ""
    }]
}

AMAP_EMPTY_RESPONSE = {
    "status": "1",
    "info": "OK",
    "geocodes": []
}

AMAP_INVALID_KEY_RESPONSE = {
    "status": "0",
    "info": "INVALID_USER_KEY",
    "infocode": "10001"
}

AMAP_QUOTA_EXCEEDED_RESPONSE = {
    "status": "0",
    "info": "DAILY_QUERY_OVER_LIMIT",
    "infocode": "10003"
}

AMAP_UNKNOWN_ERROR_RESPONSE = {
    "status": "0",
    "info": "Unknown error",
    "infocode": "10000"
}

AMAP_MALFORMED_LOCATION_RESPONSE = {
    "status": "1",
    "info": "OK",
    "geocodes": [{
        "formatted_address": "测试地址",
        "location": "",  # 空的location字段
        "province": "北京市"
    }]
}

AMAP_MISSING_LOCATION_RESPONSE = {
    "status": "1",
    "info": "OK",
    "geocodes": [{
        "formatted_address": "测试地址"
        # 没有location字段
    }]
}

# 天地图 API 响应
TIANDITU_SUCCESS_RESPONSE = {
    "status": "0",
    "msg": "ok",
    "location": {
        "lon": 116.4699,
        "lat": 39.9059,
        "address": "北京市朝阳区建国路88号",
        "province": "北京市",
        "city": "朝阳区",
        "county": ""
    }
}

TIANDITU_SUCCESS_RESPONSE_SIMPLE = {
    "status": "0",
    "msg": "ok",
    "location": {
        "lon": 116.4853,
        "lat": 39.9289,
        "address": "北京市朝阳区",
        "province": "北京市",
        "city": "朝阳区",
        "county": ""
    }
}

TIANDITU_NO_RESULT_RESPONSE = {
    "status": "1",
    "msg": "未找到相关结果"
}

TIANDITU_ERROR_RESPONSE = {
    "status": "1",
    "msg": "服务器错误"
}

TIANDITU_INVALID_KEY_RESPONSE = {
    "status": "1",
    "msg": "key错误"
}

# 百度地图 API 响应
BAIDU_SUCCESS_RESPONSE = {
    "status": 0,
    "message": "ok",
    "result": {
        "location": {
            "lng": 116.4699,
            "lat": 39.9059
        },
        "formatted_address": "北京市朝阳区建国路88号",
        "business": "",
        "addressComponent": {
            "province": "北京市",
            "city": "北京市",
            "district": "朝阳区",
            "street": "",
            "streetNumber": ""
        }
    }
}

BAIDU_SUCCESS_RESPONSE_SIMPLE = {
    "status": 0,
    "message": "ok",
    "result": {
        "location": {
            "lng": 116.4853,
            "lat": 39.9289
        },
        "formatted_address": "北京市朝阳区"
    }
}

BAIDU_INVALID_AK_RESPONSE = {
    "status": 200,
    "message": "AK不存在"
}

BAIDU_QUOTA_EXCEEDED_RESPONSE = {
    "status": 301,
    "message": "配额超限"
}

BAIDU_NO_RESULT_RESPONSE = {
    "status": 0,
    "message": "ok",
    "result": None
}

BAIDU_ERROR_RESPONSE = {
    "status": 1,
    "message": "内部错误"
}

# 空响应（用于测试JSON解析异常）
EMPTY_RESPONSE = ""

INVALID_JSON_RESPONSE = "{invalid json content"

# HTTP 错误状态码模拟
HTTP_500_ERROR = {
    "status": "500",
    "info": "Internal Server Error"
}

HTTP_403_FORBIDDEN = {
    "status": "403",
    "info": "Forbidden"
}