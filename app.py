from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from dotenv import load_dotenv
import os
import json
import logging
import shutil
import aiohttp
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum
import threading
from logging.handlers import RotatingFileHandler
import asyncio
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import requests

# 創建logs目錄
os.makedirs('logs', exist_ok=True)

# 設置日誌格式
formatter = logging.Formatter(
    '%(asctime)s - %(threadName)s - %(levelname)s - %(message)s'
)

# 配置文件處理器
file_handler = RotatingFileHandler(
    'logs/app.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
file_handler.setFormatter(formatter)

# 配置控制台處理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# 設置logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# 加載環境變數
load_dotenv()
API_KEY = os.getenv('API_KEY')

# 加載模板配置
def load_templates():
    """加載模板配置檔案"""
    try:
        templates_path = os.path.join(os.path.dirname(__file__), 'templates.json')
        with open(templates_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {t['template_id']: t for t in data['templates']}
    except Exception as e:
        logger.error(f"載入模板配置失敗: {e}")
        return {}

TEMPLATES = load_templates()
logger.info(f"已載入 {len(TEMPLATES)} 個模板配置")

def get_template_config(template_id: int) -> Optional[Dict]:
    """根據 template_id 獲取模板配置"""
    template = TEMPLATES.get(template_id)
    if not template:
        logger.warning(f"模板 ID {template_id} 不存在")
        return None
    return template

class TaskState(Enum):
    COMPLETED = 10
    FAILED = 20
    PROCESSING = 30

app = FastAPI(
    title="A1.art API 包裝服務",
    description="""
    基於 FastAPI 的 A1.art AI 圖片生成服務包裝器。

    ## 功能特色

    * **圖片上傳**: 支援多種格式圖片上傳至 A1.art 平台
    * **AI 圖片生成**: 基於上傳圖片進行 AI 風格轉換和生成
    * **模板管理**: 使用預設模板快速生成圖片
    * **任務狀態追蹤**: 即時查詢圖片生成任務的執行狀態

    ## 使用方式

    1. 使用 **POST /generate** (推薦) 或 **POST /create** 創建圖片生成任務
    2. 使用 **GET /status/{task_id}** 查詢任務狀態
    3. 使用 **GET /templates** 查看所有可用模板
    """,
    version="1.0.0",
    contact={
        "name": "API 支援",
    },
    license_info={
        "name": "僅供學習和開發使用",
    },
)

# 添加 CORS 中間件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允許所有來源
    allow_credentials=True,
    allow_methods=["*"],  # 允許所有方法
    allow_headers=["*"],  # 允許所有標頭
)

# 創建 static 目錄
os.makedirs('static', exist_ok=True)

# 掛載靜態檔案
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get(
    "/",
    summary="前端頁面",
    response_description="返回 AI 圖片生成器前端頁面",
    tags=["網頁介面"],
    include_in_schema=False
)
async def root():
    """
    提供 AI 圖片生成器的網頁介面。

    訪問此路徑可以使用圖形化介面進行圖片生成操作。
    """
    return FileResponse("static/index.html")

async def generate_image(cnet_data, description_data, style_id, size_id, app_id, version_id, generate_num):
    """生成圖片的主要函數"""
    url = "https://a1.art/open-api/v1/a1/images/generate"
    
    payload = {
        "cnet": cnet_data,
        "description": description_data,
        "styleId": style_id,
        "size": {"sizeId": size_id},
        "appId": app_id,
        "versionId": version_id,
        "generateNum": generate_num
    }
    
    headers = {
        'apiKey': API_KEY,
        'Content-Type': 'application/json',
        'Accept': '*/*',
        'Host': 'a1.art',
        'Connection': 'keep-alive'
    }
    
    try:
        logger.info("Sending request to A1.art API")
        logger.info(f"發送到 A1.art 的 payload: {json.dumps(payload, indent=2)}")
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                result = await response.json()
                if response.status != 200:
                    raise HTTPException(status_code=response.status, detail=result.get('msg_cn', '未知錯誤'))
                return result
    except Exception as e:
        logger.error(f"Error making request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def upload_image(file_path: str):
    """上傳圖片到A1.art服務器"""
    url = "https://a1.art/open-api/v1/a1/images/upload"
    
    headers = {
        'apiKey': API_KEY
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field('file',
                             f,
                             filename=os.path.basename(file_path),
                             content_type='image/jpeg')
                
                async with session.post(url, headers=headers, data=data) as response:
                    result = await response.json()
                    
                    if result.get('code') == 0:
                        logger.info("圖片上傳成功")
                        return result.get('data')
                    else:
                        error_msg = result.get('msg_cn', '未知錯誤')
                        logger.error(f"圖片上傳失敗: {error_msg}")
                        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        logger.error(f"上傳圖片時發生錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def save_uploaded_file(upload_file: UploadFile, destination: str) -> str:
    """保存上傳的檔案到指定位置"""
    try:
        with open(destination, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        return destination
    except Exception as e:
        logger.error(f"保存檔案失敗: {e}")
        raise HTTPException(status_code=500, detail=f"檔案保存失敗: {str(e)}")

async def check_task_result(task_id: str, is_china: bool = False) -> Optional[Dict]:
    """查詢任務執行結果"""
    url = f"https://a1.art/open-api/v1/a1/tasks/{task_id}"
    headers = {
        'apiKey': API_KEY,
        'Content-Type': 'application/json'
    }
    
    if is_china:
        headers["section"] = "cn"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                result = await response.json()
                
                if result.get('code') == 0:
                    return result.get('data')
                else:
                    logger.error(f"查詢任務失敗: {result.get('msg_cn', '未知錯誤')}")
                    raise HTTPException(status_code=400, detail=result.get('msg_cn', '未知錯誤'))
    except Exception as e:
        logger.error(f"查詢任務時發生錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post(
    "/create",
    summary="創建圖片生成任務（自訂參數）",
    response_description="返回任務 ID 和上傳結果",
    tags=["圖片生成"]
)
async def create_process(
    file: UploadFile = File(..., description="要上傳的圖片檔案（JPG、PNG 等格式）"),
    app_id: str = Form(default="1920079111241039873", description="A1.art 應用 ID"),
    version_id: str = Form(default="1920079111245234177", description="版本 ID"),
    cnet_form_id: str = Form(default="17466175263110005", description="ControlNet 表單 ID"),
    generate_num: int = Form(default=1, description="生成圖片數量（預設為 1）")
):
    """
    使用自訂參數創建圖片生成任務。

    上傳圖片並指定 A1.art 的應用參數來生成 AI 圖片。

    ## 參數說明
    - **file**: 要處理的圖片檔案
    - **app_id**: A1.art 應用 ID（可選，使用預設值）
    - **version_id**: 應用版本 ID（可選，使用預設值）
    - **cnet_form_id**: ControlNet 表單 ID（可選，使用預設值）
    - **generate_num**: 要生成的圖片數量（預設為 1）

    ## 回應
    返回包含任務 ID 的 JSON 物件，可用於後續查詢任務狀態。

    ## 注意事項
    - 建議使用 `/generate` 端點搭配模板 ID，更簡單方便
    - 三個參數（app_id、version_id、cnet_form_id）建議一起修改
    """
    try:
        logger.info(f"接收到的參數: app_id={app_id}, version_id={version_id}, cnet_form_id={cnet_form_id}, generate_num={generate_num}")
        # 保存上傳的檔案
        os.makedirs("input", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = os.path.splitext(file.filename)[1]
        new_filename = f"{timestamp}{file_extension}"
        file_path = os.path.join("input", new_filename)
        
        await save_uploaded_file(file, file_path)
        logger.info(f"檔案已保存到: {file_path}")
        
        # 上傳圖片
        upload_result = await upload_image(file_path)
        
        # 構建cnet參數
        cnet = [{
            "id": cnet_form_id,
            "imageUrl": upload_result["imageUrl"],
            "path": upload_result["path"]
        }]
        
        # 生成圖片
        generation_result = await generate_image(
            cnet_data=cnet,
            description_data=[],
            style_id="",
            size_id="",
            app_id=app_id,
            version_id=version_id,
            generate_num=generate_num
        )

        logger.info(f"API 回應: {json.dumps(generation_result, ensure_ascii=False, indent=2)}")

        # 檢查回應結構
        if not generation_result:
            raise HTTPException(status_code=400, detail="API 回應為空")

        if generation_result.get('code') != 0:
            error_msg = generation_result.get('msg_cn') or generation_result.get('msg') or '未知錯誤'
            logger.error(f"API 返回錯誤: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        data = generation_result.get('data')
        if not data:
            logger.error(f"API 回應中沒有 data 字段: {generation_result}")
            raise HTTPException(status_code=400, detail="API 回應格式錯誤：缺少 data 字段")

        task_id = data.get("taskId")
        if not task_id:
            logger.error(f"data 中沒有 taskId: {data}")
            raise HTTPException(status_code=400, detail="未獲取到任務ID")

        logger.info(f"成功創建任務，任務ID: {task_id}")

        return {
            "status": "success",
            "task_id": task_id,
            "upload_result": upload_result,
            "local_path": file_path
        }
        
    except Exception as e:
        logger.error(f"創建任務時發生錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post(
    "/generate",
    summary="使用模板創建圖片生成任務（推薦）",
    response_description="返回任務 ID、模板資訊和上傳結果",
    tags=["圖片生成"]
)
async def generate_with_template(
    file: UploadFile = File(..., description="要上傳的圖片檔案（JPG、PNG 等格式）"),
    template_id: int = Form(default=0, description="模板 ID（使用 /templates 查看可用模板）")
):
    """
    使用預設模板創建圖片生成任務（推薦使用）。

    只需上傳圖片並選擇模板 ID，系統會自動使用對應的參數配置。

    ## 參數說明
    - **file**: 要處理的圖片檔案
    - **template_id**: 模板 ID（預設為 0）
      - 使用 `GET /templates` 端點查看所有可用模板

    ## 優點
    - 更簡單：只需指定模板 ID
    - 更安全：避免參數配置錯誤
    - 更方便：預設配置已優化

    ## 回應
    返回包含任務 ID、模板名稱和上傳結果的 JSON 物件。

    ## 工作流程
    1. 上傳圖片到 A1.art 平台
    2. 根據模板 ID 載入預設參數
    3. 創建圖片生成任務
    4. 返回任務 ID 供後續查詢
    """
    try:
        logger.info(f"接收到的模板 ID: {template_id}")

        # 根據 template_id 獲取模板配置
        template = get_template_config(template_id)
        if not template:
            raise HTTPException(status_code=400, detail=f"模板 ID {template_id} 不存在")

        app_id = template['app_id']
        version_id = template['version_id']
        cnet_form_id = template['cnet_form_id']

        logger.info(f"使用模板: {template.get('name', f'模板 {template_id}')}")
        logger.info(f"參數: app_id={app_id}, version_id={version_id}, cnet_form_id={cnet_form_id}")

        # 保存上傳的檔案
        os.makedirs("input", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = os.path.splitext(file.filename)[1]
        new_filename = f"{timestamp}{file_extension}"
        file_path = os.path.join("input", new_filename)

        await save_uploaded_file(file, file_path)
        logger.info(f"檔案已保存到: {file_path}")

        # 上傳圖片
        upload_result = await upload_image(file_path)

        # 構建cnet參數
        cnet = [{
            "id": cnet_form_id,
            "imageUrl": upload_result["imageUrl"],
            "path": upload_result["path"]
        }]

        # 生成圖片，固定使用 generate_num = 1
        generation_result = await generate_image(
            cnet_data=cnet,
            description_data=[],
            style_id="",
            size_id="",
            app_id=app_id,
            version_id=version_id,
            generate_num=1
        )

        logger.info(f"API 回應: {json.dumps(generation_result, ensure_ascii=False, indent=2)}")

        # 檢查回應結構
        if not generation_result:
            raise HTTPException(status_code=400, detail="API 回應為空")

        if generation_result.get('code') != 0:
            error_msg = generation_result.get('msg_cn') or generation_result.get('msg') or '未知錯誤'
            logger.error(f"API 返回錯誤: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        data = generation_result.get('data')
        if not data:
            logger.error(f"API 回應中沒有 data 字段: {generation_result}")
            raise HTTPException(status_code=400, detail="API 回應格式錯誤：缺少 data 字段")

        task_id = data.get("taskId")
        if not task_id:
            logger.error(f"data 中沒有 taskId: {data}")
            raise HTTPException(status_code=400, detail="未獲取到任務ID")

        logger.info(f"成功創建任務，任務ID: {task_id}, 使用模板: {template.get('name', f'模板 {template_id}')}")

        return {
            "status": "success",
            "task_id": task_id,
            "template_id": template_id,
            "template_name": template.get('name', f'模板 {template_id}'),
            "upload_result": upload_result,
            "local_path": file_path
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"使用模板創建任務時發生錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get(
    "/templates",
    summary="查詢所有可用模板",
    response_description="返回所有模板的配置資訊",
    tags=["模板管理"]
)
async def get_templates():
    """
    獲取所有可用的模板配置清單。

    返回系統中所有已配置的模板，包括模板 ID、名稱和參數資訊。

    ## 回應
    返回包含所有模板資訊的 JSON 陣列，每個模板包含：
    - **template_id**: 模板 ID
    - **name**: 模板名稱
    - **app_id**: A1.art 應用 ID
    - **version_id**: 版本 ID
    - **cnet_form_id**: ControlNet 表單 ID
    - **template_image**: 模板預覽圖片路徑（可能為 null）

    ## 使用方式
    1. 調用此端點獲取所有可用模板
    2. 選擇需要的模板 ID
    3. 使用該 ID 調用 `POST /generate` 生成圖片
    """
    try:
        templates_list = [
            {
                "template_id": template_id,
                "name": config.get("name", f"模板 {template_id}"),
                "app_id": config["app_id"],
                "version_id": config["version_id"],
                "cnet_form_id": config["cnet_form_id"],
                "template_image": config.get("template_image")
            }
            for template_id, config in sorted(TEMPLATES.items())
        ]
        return {
            "status": "success",
            "count": len(templates_list),
            "templates": templates_list
        }
    except Exception as e:
        logger.error(f"獲取模板列表時發生錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get(
    "/status/{task_id}",
    summary="查詢任務狀態",
    response_description="返回任務執行狀態和生成的圖片",
    tags=["任務管理"]
)
async def get_process_status(task_id: str):
    """
    查詢圖片生成任務的執行狀態。

    使用創建任務時返回的任務 ID 來查詢任務進度和結果。

    ## 參數說明
    - **task_id**: 任務 ID（從 `/create` 或 `/generate` 端點獲得）

    ## 任務狀態
    - **10 (COMPLETED)**: 任務完成，圖片已生成
    - **20 (FAILED)**: 任務失敗
    - **30 (PROCESSING)**: 處理中，請繼續輪詢

    ## 回應
    返回任務狀態資訊：
    - **status**: 請求狀態
    - **id**: 任務 ID
    - **state**: 狀態碼（10/20/30）
    - **state_text**: 狀態文字（COMPLETED/FAILED/PROCESSING）
    - **images**: 生成的圖片 URL 陣列（僅在 COMPLETED 時返回）
    - **startDate**: 開始時間
    - **finishDate**: 完成時間
    - **createDate**: 創建時間

    ## 使用建議
    - 建議每 2 秒輪詢一次
    - 狀態為 PROCESSING 時繼續輪詢
    - 狀態為 COMPLETED 時獲取圖片 URL
    - 狀態為 FAILED 時停止輪詢
    """
    try:
        task_result = await check_task_result(task_id, is_china=True)
        
        state = task_result.get("state")
        
        if state == TaskState.COMPLETED.value:  # state == 10
            logger.info(f"TaskId: {task_id} 任務完成")
            images = task_result.get("images", [])
            logger.info(f"返回的圖片數量: {len(images)}")
            if images:
                logger.info(f"圖片數據結構: {json.dumps(images, ensure_ascii=False, indent=2)}")

            response = {
                "status": "success",
                "id": task_result.get("id"),
                "state_text": TaskState(state).name if state in [s.value for s in TaskState] else "UNKNOWN",
                "state": state,
                "startDate": task_result.get("startDate"),
                "finishDate": task_result.get("finishDate"),
                "createDate": task_result.get("createDate"),
                "images": images
            }
            # 任務完成時返回完整資訊
            return response
        else:  # state == 20 or state == 30
            # 其他狀態只返回基本資訊
            response = {
                "status": "success",
                "id": task_result.get("id"),
                "state_text": TaskState(state).name if state in [s.value for s in TaskState] else "UNKNOWN",
                "state": state,
                "startDate": task_result.get("startDate"),
                "finishDate": task_result.get("finishDate"),
                "createDate": task_result.get("createDate"),
                "images": task_result.get("images", [])
            }
            logger.info(f"TaskId: {task_id} 任務狀態: {response['state_text']}")
            return response
        
    except Exception as e:
        logger.error(f"檢查任務狀態時發生錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=1989)
