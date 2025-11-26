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

class TaskState(Enum):
    COMPLETED = 10
    FAILED = 20    
    PROCESSING = 30

app = FastAPI()

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

@app.get("/")
async def root():
    """提供前端頁面"""
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

@app.post("/create")
async def create_process(
    file: UploadFile = File(...),
    app_id: str = Form(default="1920079111241039873"), 
    version_id: str = Form(default="1920079111245234177"),
    cnet_form_id: str = Form(default="17466175263110005"),
    generate_num: int = Form(default=1)
):
    """創建圖片生成任務"""
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

@app.get("/status/{task_id}")
async def get_process_status(task_id: str):
    """獲取任務狀態"""
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
