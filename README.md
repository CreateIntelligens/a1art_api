# A1.art API 包裝服務

基於 FastAPI 的 A1.art AI 圖片生成服務包裝器，提供圖片上傳和 AI 圖片生成功能。

## 功能特色

- 🖼️ **圖片上傳**: 支援多種格式圖片上傳至 A1.art 平台
- 🎨 **AI 圖片生成**: 基於上傳圖片進行 AI 風格轉換和生成
- 📊 **任務狀態追蹤**: 即時查詢圖片生成任務的執行狀態
- 📝 **完整日誌**: 使用 RotatingFileHandler 記錄詳細操作日誌
- 🚀 **異步處理**: 使用 aiohttp 提供高效的異步 API 請求

## 系統要求

- Python 3.7+
- A1.art API Key

## 安裝與設置

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

### 2. 環境配置

在專案根目錄創建 `.env` 檔案：

```env
API_KEY=your_a1_art_api_key_here
```

### 3. 模板配置

複製 `templates_sample.json` 為 `templates.json` 並根據需求修改模板參數：

```bash
cp templates_sample.json templates.json
```

編輯 `templates.json` 設定你的模板：

```json
{
  "templates": [
    {
      "template_id": 0,
      "name": "你的模板名稱",
      "app_id": "你的 app_id",
      "version_id": "你的 version_id",
      "cnet_form_id": "你的 cnet_form_id",
      "template_image": "/static/template_images/your_template_image.jpg"
    }
  ]
}
```

**模板參數說明**：
- `template_id`: 模板 ID（必需）
- `name`: 模板名稱（必需）
- `app_id`: A1.art 應用 ID（必需）
- `version_id`: 版本 ID（必需）
- `cnet_form_id`: ControlNet 表單 ID（必需）
- `template_image`: 模板預覽圖片路徑（選填）
  - 圖片應放在 `static/template_images/` 目錄下
  - 路徑格式：`/static/template_images/your_image.jpg`
  - **建議使用 3:4 比例的圖片**（例如：600x800、900x1200）以獲得最佳顯示效果
  - 前端會以 `aspect-ratio: 3/4` 完整顯示圖片，不會裁切
  - 如果不提供圖片，模板卡片將只顯示文字

**重要**：
- `templates.json` 包含你的實際模板配置，**不會**上傳到 Git（已加入 .gitignore）
- `templates_sample.json` 是範例檔案，可以安全地提交到 Git
- `static/template_images/` 目錄中的圖片**不會**上傳到 Git（已加入 .gitignore）
- 修改模板後需要重新啟動服務才會生效

### 4. 啟動服務

```bash
python app.py
```

服務將在 `http://localhost:1991` 啟動。

## API 使用說明

### 1. 創建圖片生成任務

**端點**: `POST /create`

**參數**:
- `file`: 上傳的圖片檔案 (必需)
- `app_id`: A1.art 應用 ID (預設: "1912088126456299522")
- `version_id`: 版本 ID (預設: "1912088126460493825")  
- `cnet_form_id`: ControlNet 表單 ID (預設: "17447123252810005")
- `generate_num`: 生成圖片數量 (預設: 1)

**請求範例**:

```bash
curl -X POST "http://localhost:1991/create" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@your_image.jpg" \
  -F "app_id=1912088126456299522" \
  -F "version_id=1912088126460493825" \
  -F "cnet_form_id=17447123252810005" \
  -F "generate_num=1"
```

**回應範例**:

```json
{
  "status": "success",
  "task_id": "task_12345678",
  "upload_result": {
    "imageUrl": "https://a1.art/path/to/uploaded/image.jpg",
    "path": "/uploads/image.jpg"
  },
  "local_path": "input/20231125_142530.jpg"
}
```

### 2. 使用模板創建圖片生成任務 (推薦)

**端點**: `POST /generate`

**參數**:
- `file`: 上傳的圖片檔案 (必需)
- `template_id`: 模板 ID (預設: 0)

**請求範例**:

```bash
curl -X POST "http://localhost:1991/generate" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@your_image.jpg" \
  -F "template_id=0"
```

**回應範例**:

```json
{
  "status": "success",
  "task_id": "task_12345678",
  "template_id": 0,
  "template_name": "測試模板-JOJO",
  "upload_result": {
    "imageUrl": "https://a1.art/path/to/uploaded/image.jpg",
    "path": "/uploads/image.jpg"
  },
  "local_path": "input/20231125_142530.jpg"
}
```

**說明**:
- 使用模板 ID 自動查找對應的 `app_id`、`version_id`、`cnet_form_id`
- 更簡單、更不容易出錯
- `generate_num` 固定為 1

### 3. 查詢所有可用模板

**端點**: `GET /templates`

**請求範例**:

```bash
curl "http://localhost:1991/templates"
```

**回應範例**:

```json
{
  "status": "success",
  "count": 4,
  "templates": [
    {
      "template_id": 0,
      "name": "測試模板-JOJO",
      "app_id": "1940002918948761602",
      "version_id": "1940002918952955905",
      "cnet_form_id": "17361503364050001"
    }
  ]
}
```

### 4. 查詢任務狀態

**端點**: `GET /status/{task_id}`

**請求範例**:

```bash
curl "http://localhost:1991/status/task_12345678"
```

**回應範例** (處理中):

```json
{
  "status": "success",
  "id": "task_12345678",
  "state_text": "PROCESSING",
  "state": 30,
  "startDate": "2023-11-25T14:25:30Z",
  "finishDate": null,
  "createDate": "2023-11-25T14:25:25Z",
  "images": []
}
```

**回應範例** (完成):

```json
{
  "status": "success",
  "id": "task_12345678",
  "state_text": "COMPLETED",
  "state": 10,
  "startDate": "2023-11-25T14:25:30Z",
  "finishDate": "2023-11-25T14:27:45Z",
  "createDate": "2023-11-25T14:25:25Z",
  "images": [
    {
      "url": "https://a1.art/generated/image1.jpg",
      "thumbnail": "https://a1.art/generated/image1_thumb.jpg"
    }
  ]
}
```

### 任務狀態說明

| 狀態碼 | 狀態名稱 | 說明 |
|-------|---------|------|
| 10 | COMPLETED | 任務完成 |
| 20 | FAILED | 任務失敗 |
| 30 | PROCESSING | 處理中 |

## 目錄結構

```
├── app.py                      # 主應用程式
├── requirements.txt            # Python 依賴包
├── .env                        # 環境變數配置
├── templates.json              # 模板配置檔案（不上傳到 Git）
├── templates_sample.json       # 模板配置範例檔案
├── docker-compose.yaml         # Docker 配置
├── Dockerfile                  # Docker 映像配置
├── input/                      # 上傳檔案存放目錄
│   └── .gitkeep                # 確保目錄被 git 追蹤
├── logs/                       # 日誌檔案目錄
│   └── .gitkeep                # 確保目錄被 git 追蹤
├── static/                     # 靜態檔案目錄
│   ├── index.html              # 前端頁面
│   └── template_images/        # 模板預覽圖片目錄（圖片不上傳到 Git）
│       └── .gitkeep            # 確保目錄被 git 追蹤
└── README.md                   # 專案說明文檔
```

## Docker 部署

### 使用 Docker Compose

```bash
# 啟動服務
docker-compose up -d

# 查看日誌
docker-compose logs -f

# 停止服務
docker-compose down
```

### 環境變數

在使用 Docker 部署時，請確保在 `.env` 檔案中設置了正確的 `API_KEY`：

```env
API_KEY=your_a1_art_api_key_here
```

## 日誌系統

應用程式使用 RotatingFileHandler 進行日誌管理：

- **日誌檔案**: `logs/app.log`
- **檔案大小限制**: 10MB
- **備份數量**: 5 個
- **日誌格式**: `時間 - 執行緒名稱 - 日誌等級 - 訊息內容`

日誌會同時輸出到控制台和檔案，方便開發和生產環境的監控。

## 開發說明

### 本地開發

```bash
# 安裝開發依賴
pip install -r requirements.txt

# 啟動開發服務器
python app.py
```

### API 文檔與測試

本服務提供完整的 API 互動式文檔，方便開發和測試：

#### Swagger UI（推薦）
- **網址**: `http://localhost:1991/docs`
- **功能**:
  - 📖 查看所有 API 端點詳細說明
  - 🧪 直接在瀏覽器中測試 API
  - 📝 查看請求/回應範例
  - 🔧 測試檔案上傳功能
  - 📊 查看資料模型結構

#### ReDoc
- **網址**: `http://localhost:1991/redoc`
- **功能**:
  - 📚 美觀的 API 文檔閱讀介面
  - 🔍 搜尋功能
  - 📋 更適合文檔閱讀

#### API 端點分類
- **圖片生成**: `/create`、`/generate`
- **任務管理**: `/status/{task_id}`
- **模板管理**: `/templates`
- **網頁介面**: `/`（前端頁面）

## 錯誤處理

服務包含完整的錯誤處理機制：

- **400 Bad Request**: 參數錯誤或 A1.art API 請求失敗
- **500 Internal Server Error**: 服務內部錯誤
- **詳細錯誤訊息**: 所有錯誤都會記錄在日誌中並返回給客戶端

## 注意事項

1. **API Key**: 請確保設置正確的 A1.art API Key
2. **檔案大小**: 注意上傳檔案的大小限制
3. **任務超時**: 圖片生成可能需要一些時間，請耐心等待
4. **日誌監控**: 定期檢查日誌檔案以監控服務運行狀態

## 授權

此專案僅供學習和開發使用。請遵循 A1.art 的服務條款和使用限制。
