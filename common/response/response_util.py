from fastapi import status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel
from typing import Any, Dict, Optional

from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN, HTTP_500_INTERNAL_SERVER_ERROR, HTTP_200_OK

from common.utils.time_format_util import parse_and_format_date


class ResponseUtil:
    """
    响应工具类
    """

    @classmethod
    def success(
        cls,
        msg: str = 'Success',
        data: Optional[Any] = None,
        rows: Optional[Any] = None,
        dict_content: Optional[Dict] = None,
        model_content: Optional[BaseModel] = None,
    ) -> Response:
        """
        成功响应方法

        :param msg: 可选，自定义成功响应信息
        :param data: 可选，成功响应结果中属性为data的值
        :param rows: 可选，成功响应结果中属性为rows的值
        :param dict_content: 可选，dict类型，成功响应结果中自定义属性的值
        :param model_content: 可选，BaseModel类型，成功响应结果中自定义属性的值
        :return: 成功响应结果
        """
        result = {'code': HTTP_200_OK, 'msg': msg}

        if data is not None:
            result['data'] = data
        if rows is not None:
            result['rows'] = rows
        if dict_content is not None:
            result.update(dict_content)
        if model_content is not None:
            result.update(model_content.model_dump())

        result.update({'success': True, 'time': parse_and_format_date()})

        return JSONResponse(status_code=status.HTTP_200_OK, content=jsonable_encoder(result))

    @classmethod
    def failure(
        cls,
        msg: str = 'Bad Request',
        data: Optional[Any] = None,
        rows: Optional[Any] = None,
        dict_content: Optional[Dict] = None,
        model_content: Optional[BaseModel] = None,
    ) -> Response:
        """
        失败响应方法

        :param msg: 可选，自定义失败响应信息
        :param data: 可选，失败响应结果中属性为data的值
        :param rows: 可选，失败响应结果中属性为rows的值
        :param dict_content: 可选，dict类型，失败响应结果中自定义属性的值
        :param model_content: 可选，BaseModel类型，失败响应结果中自定义属性的值
        :return: 失败响应结果
        """
        result = {'code': status.HTTP_400_BAD_REQUEST, 'msg': msg}

        if data is not None:
            result['data'] = data
        if rows is not None:
            result['rows'] = rows
        if dict_content is not None:
            result.update(dict_content)
        if model_content is not None:
            result.update(model_content.model_dump())

        result.update({'success': False, 'time': parse_and_format_date()})

        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=jsonable_encoder(result))

    @classmethod
    def failure_ok(
        cls,
        msg: str = 'Bad Request',
        data: Optional[Any] = None,
        rows: Optional[Any] = None,
        dict_content: Optional[Dict] = None,
        model_content: Optional[BaseModel] = None,
    ) -> Response:
        """
        Business failure response with HTTP 200 and body code 400.
        """
        result = {'code': status.HTTP_400_BAD_REQUEST, 'msg': msg}

        if data is not None:
            result['data'] = data
        if rows is not None:
            result['rows'] = rows
        if dict_content is not None:
            result.update(dict_content)
        if model_content is not None:
            result.update(model_content.model_dump())

        result.update({'success': False, 'time': parse_and_format_date()})

        return JSONResponse(status_code=status.HTTP_200_OK, content=jsonable_encoder(result))

    @classmethod
    def special_failure(
            cls,
            msg: str = 'Bad Request',
            data: Optional[Any] = None,
            rows: Optional[Any] = None,
            dict_content: Optional[Dict] = None,
            model_content: Optional[BaseModel] = None,
    ) -> Response:
        """
        失败响应方法

        :param msg: 可选，自定义失败响应信息
        :param data: 可选，失败响应结果中属性为data的值
        :param rows: 可选，失败响应结果中属性为rows的值
        :param dict_content: 可选，dict类型，失败响应结果中自定义属性的值
        :param model_content: 可选，BaseModel类型，失败响应结果中自定义属性的值
        :return: 失败响应结果
        """
        result = {'code': 466, 'msg': msg}

        if data is not None:
            result['data'] = data
        if rows is not None:
            result['rows'] = rows
        if dict_content is not None:
            result.update(dict_content)
        if model_content is not None:
            result.update(model_content.model_dump())

        result.update({'success': False, 'time': parse_and_format_date()})

        return JSONResponse(status_code=466, content=jsonable_encoder(result))

    @classmethod
    def unauthorized(
        cls,
        msg: str = '登录信息已过期，访问系统资源失败',
        data: Optional[Any] = None,
        rows: Optional[Any] = None,
        dict_content: Optional[Dict] = None,
        model_content: Optional[BaseModel] = None,
    ) -> Response:
        """
        未认证响应方法

        :param msg: 可选，自定义未认证响应信息
        :param data: 可选，未认证响应结果中属性为data的值
        :param rows: 可选，未认证响应结果中属性为rows的值
        :param dict_content: 可选，dict类型，未认证响应结果中自定义属性的值
        :param model_content: 可选，BaseModel类型，未认证响应结果中自定义属性的值
        :return: 未认证响应结果
        """
        result = {'code': HTTP_401_UNAUTHORIZED, 'msg': msg}

        if data is not None:
            result['data'] = data
        if rows is not None:
            result['rows'] = rows
        if dict_content is not None:
            result.update(dict_content)
        if model_content is not None:
            result.update(model_content.model_dump())

        result.update({'success': False, 'time': parse_and_format_date()})

        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content=jsonable_encoder(result))

    @classmethod
    def forbidden(
        cls,
        msg: str = '该用户无此接口权限',
        data: Optional[Any] = None,
        rows: Optional[Any] = None,
        dict_content: Optional[Dict] = None,
        model_content: Optional[BaseModel] = None,
    ) -> Response:
        """
        未授权响应方法

        :param msg: 可选，自定义未授权响应信息
        :param data: 可选，未授权响应结果中属性为data的值
        :param rows: 可选，未授权响应结果中属性为rows的值
        :param dict_content: 可选，dict类型，未授权响应结果中自定义属性的值
        :param model_content: 可选，BaseModel类型，未授权响应结果中自定义属性的值
        :return: 未授权响应结果
        """
        result = {'code': HTTP_403_FORBIDDEN, 'msg': msg}

        if data is not None:
            result['data'] = data
        if rows is not None:
            result['rows'] = rows
        if dict_content is not None:
            result.update(dict_content)
        if model_content is not None:
            result.update(model_content.model_dump())

        result.update({'success': False, 'time': parse_and_format_date()})

        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content=jsonable_encoder(result))

    @classmethod
    def error(
        cls,
        msg: str = '接口异常',
        data: Optional[Any] = None,
        rows: Optional[Any] = None,
        dict_content: Optional[Dict] = None,
        model_content: Optional[BaseModel] = None,
    ) -> Response:
        """
        错误响应方法

        :param msg: 可选，自定义错误响应信息
        :param data: 可选，错误响应结果中属性为data的值
        :param rows: 可选，错误响应结果中属性为rows的值
        :param dict_content: 可选，dict类型，错误响应结果中自定义属性的值
        :param model_content: 可选，BaseModel类型，错误响应结果中自定义属性的值
        :return: 错误响应结果
        """
        result = {'code': HTTP_500_INTERNAL_SERVER_ERROR, 'msg': msg}

        if data is not None:
            result['data'] = data
        if rows is not None:
            result['rows'] = rows
        if dict_content is not None:
            result.update(dict_content)
        if model_content is not None:
            result.update(model_content.model_dump())

        result.update({'success': False, 'time': parse_and_format_date()})

        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=jsonable_encoder(result))

    @classmethod
    def streaming(cls, *, data: Any = None):
        """
        流式响应方法

        :param data: 流式传输的内容
        :return: 流式响应结果
        """
        return StreamingResponse(status_code=status.HTTP_200_OK, content=data)
