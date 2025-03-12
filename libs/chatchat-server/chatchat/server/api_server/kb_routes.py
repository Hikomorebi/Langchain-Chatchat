from __future__ import annotations

from typing import List, Literal

from fastapi import APIRouter, Request

from chatchat.settings import Settings
from chatchat.server.api_server.api_schemas import OpenAIChatInput, OpenAIChatOutput
from chatchat.server.chat.file_chat import upload_temp_docs
from chatchat.server.chat.kb_chat import kb_chat
from chatchat.server.knowledge_base.kb_api import create_kb, delete_kb, list_kbs
from chatchat.server.knowledge_base.kb_doc_api import (
    delete_docs,
    download_doc,
    list_files,
    recreate_vector_store,
    search_docs,
    update_docs,
    update_info,
    upload_docs,
    search_temp_docs,
)
from chatchat.server.knowledge_base.kb_summary_api import (
    recreate_summary_vector_store,
    summary_doc_ids_to_vector_store,
    summary_file_to_vector_store,
)
from chatchat.server.utils import BaseResponse, ListResponse
from chatchat.server.knowledge_base.kb_cache.faiss_cache import memo_faiss_pool

from pydantic import BaseModel, Field
from typing import Dict
from json import loads

kb_router = APIRouter(prefix="/knowledge_base", tags=["Knowledge Base Management"])

@kb_router.post(
    "/{mode}/{param}/chat/completions", summary="知识库对话，openai 兼容，参数与 /chat/kb_chat 一致"
)
async def kb_chat_endpoint(
    mode: Literal["local_kb", "temp_kb", "search_engine"],
    param: str,
    body: OpenAIChatInput,
    request: Request,
):
    # import rich
    # rich.print(body)

    if body.max_tokens in [None, 0]:
        body.max_tokens = Settings.model_settings.MAX_TOKENS

    extra = body.model_extra
    ret = await kb_chat(
        query=body.messages[-1]["content"],
        mode=mode,
        kb_name=param,
        top_k=extra.get("top_k", Settings.kb_settings.VECTOR_SEARCH_TOP_K),
        score_threshold=extra.get("score_threshold", Settings.kb_settings.SCORE_THRESHOLD),
        history=body.messages[:-1],
        stream=body.stream,
        model=body.model,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        prompt_name=extra.get("prompt_name", "default"),
        return_direct=extra.get("return_direct", False),
        request=request,
    )
    return ret

# 新增自定义请求模型
class CustomChatRequest(BaseModel):
    sessionNo: str = Field(..., description="会话唯一标识")
    content: str = Field(..., description="当前用户消息内容")
    source: int = Field(0, description="消息来源类型")
    time: str = Field(..., description="消息时间戳")
    appType: int = Field(0, description="应用类型")
    modelType: int = Field(0, description="模型类型 0-qwen-max-0125 1-deepseek-v3 2-deepseek-r1")
    history: List[Dict[str, str]] = Field(..., description="历史对话记录")

# 在现有路由中添加新端点
@kb_router.post(
    "/{mode}/{param}/custom_chat",
    response_model=OpenAIChatOutput,  # 保持与原有输出格式一致
    summary="兼容格式的知识库对话",
    tags=["Knowledge Base Management"]
)
async def custom_kb_chat(
    mode: Literal["local_kb", "temp_kb", "search_engine"],
    param: str,
    body: CustomChatRequest,
    request: Request,
):
    # 将历史记录转换为OpenAI格式（注意role映射）
    messages = []
    for msg in body.history:
        # 将原"robot"角色转换为"assistant"
        role = "assistant" if msg["role"] == "robot" else msg["role"]
        messages.append({"role": role, "content": msg["content"]})
    
    # 添加当前问题
    messages.append({"role": "user", "content": body.content})

    # 模型类型映射
    model_map = {
        0: "deepseek-v3",
        1: "qwen-max-0125",
        2: "deepseek-r1"
        # 根据实际模型配置扩展
    }

    # 构建OpenAI兼容请求体
    openai_body = OpenAIChatInput(
        model=model_map.get(body.modelType, "deepseek-v3"),
        messages=messages,
        temperature=0.7,  # 默认参数
        max_tokens=Settings.model_settings.MAX_TOKENS,
        stream=True,  # 流式
    )
    KB_MAPPING = {
    "newhope": "食品安全",
    # 更多映射...
    }
    # 复用原有业务逻辑
    result = await kb_chat(
        query=openai_body.messages[-1]["content"],
        mode=mode,
        kb_name=KB_MAPPING.get(param.lower(), param),  # 优先查映射表，无匹配则用原值
        top_k= 3, 
        score_threshold= 0.5,
        history=openai_body.messages[:-1],
        stream=openai_body.stream,
        model=openai_body.model,
        temperature=openai_body.temperature,
        max_tokens=openai_body.max_tokens,
        prompt_name= "default",
        return_direct= False,
        request=request,
    ) 
     
    if isinstance(result, str):  # 检查 result 是否为 JSON 字符串
        result = loads(result)  # 将 JSON 字符串解析为字典
        
    return result

kb_router.get(
    "/list_knowledge_bases", response_model=ListResponse, summary="获取知识库列表"
)(list_kbs)

kb_router.post(
    "/create_knowledge_base", response_model=BaseResponse, summary="创建知识库"
)(create_kb)

kb_router.post(
    "/delete_knowledge_base", response_model=BaseResponse, summary="删除知识库"
)(delete_kb)

kb_router.get(
    "/list_files", response_model=ListResponse, summary="获取知识库内的文件列表"
)(list_files)

kb_router.post("/search_docs", response_model=List[dict], summary="搜索知识库")(
    search_docs
)

kb_router.post(
    "/upload_docs",
    response_model=BaseResponse,
    summary="上传文件到知识库，并/或进行向量化",
)(upload_docs)

kb_router.post(
    "/delete_docs", response_model=BaseResponse, summary="删除知识库内指定文件"
)(delete_docs)

kb_router.post("/update_info", response_model=BaseResponse, summary="更新知识库介绍")(
    update_info
)

kb_router.post(
    "/update_docs", response_model=BaseResponse, summary="更新现有文件到知识库"
)(update_docs)

kb_router.get("/download_doc", summary="下载对应的知识文件")(download_doc)

kb_router.post(
    "/recreate_vector_store", summary="根据content中文档重建向量库，流式输出处理进度。"
)(recreate_vector_store)

kb_router.post("/upload_temp_docs", summary="上传文件到临时目录，用于文件对话。")(
    upload_temp_docs
)

kb_router.post("/search_temp_docs", summary="检索临时知识库")(
    search_temp_docs
)

# @kb_router.post("/list_temp_kbs", summary="列出所有临时知识库")
# def list_temp_kbs():
#     return list(memo_faiss_pool.keys())


summary_router = APIRouter(prefix="/kb_summary_api")
summary_router.post(
    "/summary_file_to_vector_store", summary="单个知识库根据文件名称摘要"
)(summary_file_to_vector_store)
summary_router.post(
    "/summary_doc_ids_to_vector_store",
    summary="单个知识库根据doc_ids摘要",
    response_model=BaseResponse,
)(summary_doc_ids_to_vector_store)
summary_router.post("/recreate_summary_vector_store", summary="重建单个知识库文件摘要")(
    recreate_summary_vector_store
)

kb_router.include_router(summary_router)
