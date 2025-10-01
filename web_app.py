# -*- coding: utf-8 -*-
"""
一个集成天眼查和DeepSeek API的脚本，用于查询公司信息并生成分析报告。
(已添加详细的调试日志功能)
"""

import os
import requests
import json
from flask import Flask, render_template_string, request, jsonify
from urllib.parse import quote_plus
from openai import OpenAI

# --- Flask 应用初始化 ---
app = Flask(__name__)

# --- 配置部分 ---
# 从环境变量中安全地读取API密钥和Token
TIANYANCHA_TOKEN = os.environ.get('TIANYANCHA_TOKEN')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')

# 天眼查API的URL
TIANYANCHA_API_URL = "http://open.api.tianyancha.com/services/open/ic/baseinfoV3/2.0"

# --- HTML 模板 ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>企业信息分析平台</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: 'Inter', sans-serif; }
        .loader { border-top-color: #3498db; }
    </style>
</head>
<body class="bg-gray-100 flex items-start justify-center min-h-screen p-4 sm:p-6 lg:p-8">
    <div class="bg-white w-full max-w-4xl mx-auto rounded-2xl shadow-lg p-6 sm:p-8 lg:p-10">
        <div class="text-center mb-8">
            <h1 class="text-3xl sm:text-4xl font-bold text-gray-800">企业信息分析平台</h1>
            <p class="text-gray-500 mt-2">输入公司全名，获取即时、专业的分析报告</p>
        </div>
        <div class="flex flex-col sm:flex-row gap-4 mb-6">
            <input type="text" id="companyName" placeholder="请输入完整的公司名称..." class="flex-grow w-full px-4 py-3 text-lg border-2 border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-shadow duration-200 outline-none" autofocus>
            <button id="searchButton" class="w-full sm:w-auto bg-blue-600 text-white font-semibold px-8 py-3 text-lg rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-300 transition-all duration-300 transform hover:scale-105 disabled:bg-blue-300 disabled:cursor-not-allowed">
                <span id="button-text">立即分析</span>
                <div id="button-loader" class="hidden w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin mx-auto"></div>
            </button>
        </div>
        <div id="result-container" class="mt-8 min-h-[200px] bg-gray-50 p-6 rounded-lg border border-gray-200">
            <div id="loader" class="hidden flex-col items-center justify-center text-gray-500">
                <div class="w-10 h-10 border-4 border-gray-200 border-t-blue-500 rounded-full animate-spin"></div>
                <p id="loading-status" class="mt-4 text-lg">正在努力分析中，请稍候...</p>
            </div>
            <div id="initial-prompt" class="flex flex-col items-center justify-center text-center text-gray-400">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-16 h-16 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                <p class="text-xl">分析报告将在此处显示</p>
            </div>
            <div id="error-message" class="hidden text-center text-red-600 bg-red-50 p-4 rounded-lg"></div>
            <div id="report-content"></div>
        </div>
    </div>
    <script>
        const companyNameInput = document.getElementById('companyName');
        const searchButton = document.getElementById('searchButton');
        const buttonText = document.getElementById('button-text');
        const buttonLoader = document.getElementById('button-loader');
        const loader = document.getElementById('loader');
        const loadingStatus = document.getElementById('loading-status');
        const initialPrompt = document.getElementById('initial-prompt');
        const errorMessage = document.getElementById('error-message');
        const reportContent = document.getElementById('report-content');

        searchButton.addEventListener('click', handleAnalysis);
        companyNameInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') handleAnalysis(); });

        async function handleAnalysis() {
            const companyName = companyNameInput.value.trim();
            if (!companyName) {
                showError("请输入公司名称。");
                return;
            }
            setLoadingState(true);
            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ company_name: companyName })
                });
                const data = await response.json();
                if (data.success) {
                    showReport(data.report);
                } else {
                    showError(data.error);
                }
            } catch (error) {
                showError('请求服务器失败，请稍后重试。');
            } finally {
                setLoadingState(false);
            }
        }
        function setLoadingState(isLoading) {
            searchButton.disabled = isLoading;
            buttonText.classList.toggle('hidden', isLoading);
            buttonLoader.classList.toggle('hidden', !isLoading);
            initialPrompt.classList.add('hidden');
            errorMessage.classList.add('hidden');
            reportContent.innerHTML = '';
            if(isLoading) {
                loader.classList.remove('hidden');
                loader.classList.add('flex');
            } else {
                loader.classList.add('hidden');
            }
        }
        function showError(message) {
            loader.classList.add('hidden');
            errorMessage.innerText = message;
            errorMessage.classList.remove('hidden');
        }
        function showReport(htmlContent) {
            loader.classList.add('hidden');
            reportContent.innerHTML = htmlContent;
        }
    </script>
</body>
</html>
"""


# --- 核心后端逻辑 ---

def get_company_info_from_tianyancha(company_name: str) -> dict | None:
    """通过公司名称调用天眼查API获取企业基本信息 (包含详细调试日志)。"""
    print("--- [DEBUG] Entering get_company_info_from_tianyancha ---")

    token_from_env = os.environ.get('TIANYANCHA_TOKEN')

    if not token_from_env:
        print("!!! [ERROR] TIANYANCHA_TOKEN not found in environment variables!")
        return None, "服务器错误：天眼查Token未配置。"
    else:
        # 打印部分Token以确认它被正确读取，但不暴露完整密钥
        print(
            f"--- [DEBUG] Tianyancha Token loaded. Starts with: '{token_from_env[:4]}', Ends with: '{token_from_env[-4:]}'")

    encoded_company_name = quote_plus(company_name)
    url = f"{TIANYANCHA_API_URL}?keyword={encoded_company_name}"
    print(f"--- [DEBUG] Requesting URL: {url}")

    headers = {
        'Authorization': token_from_env,
        # 新增：伪装成一个常见的浏览器User-Agent，以绕过服务器的机器人检测
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        print(f"--- [DEBUG] Received response with status code: {response.status_code}")

        response_text = response.text
        print(f"--- [DEBUG] Raw response from Tianyancha: {response_text[:500]}")  # 打印前500个字符

        data = response.json()

        if data.get("error_code") == 0:
            print("--- [DEBUG] Successfully parsed data from Tianyancha.")
            return data.get("result"), None
        else:
            error_reason = data.get('reason', '未知错误')
            print(f"!!! [ERROR] Tianyancha API returned an error. Reason: {error_reason}")
            return None, f"天眼查API错误：{error_reason}"

    except requests.exceptions.RequestException as e:
        print(f"!!! [ERROR] A network error occurred during the request to Tianyancha: {e}")
        return None, "网络错误：无法连接到天眼查服务器。"
    except json.JSONDecodeError:
        print(f"!!! [ERROR] Failed to parse JSON from Tianyancha's response.")
        return None, "服务器错误：解析天眼查返回数据失败。"


def summarize_info_with_deepseek(company_info: dict) -> str:
    """使用DeepSeek API来总结和分析公司信息。"""
    print("--- [DEBUG] Entering summarize_info_with_deepseek ---")
    if not DEEPSEEK_API_KEY:
        print("!!! [ERROR] DEEPSEEK_API_KEY not found in environment variables!")
        return "服务器错误：DeepSeek API Key未配置。"

    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

        prompt = f"""
        你是一位顶级的商业分析专家。你的任务是根据提供的企业JSON数据，生成一份专业、精炼且易于阅读的企业分析报告。
        严格遵循以下HTML格式和要求进行输出，不要有任何额外解释或Markdown标记：
        当前年份：2025年
        <div class="space-y-6">...</div> 
        请根据以下公司JSON数据开始分析: {json.dumps(company_info, ensure_ascii=False, indent=2)}
        """

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一位顶级的商业分析专家，严格按照用户指令生成格式化的HTML报告。"},
                {"role": "user", "content": prompt},
            ],
            stream=False
        )
        print("--- [DEBUG] Successfully received analysis from DeepSeek.")
        return response.choices[0].message.content
    except Exception as e:
        print(f"!!! [ERROR] An error occurred during the request to DeepSeek: {e}")
        return f"分析引擎错误：{e}"


# --- Flask 路由 ---

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    company_name = data.get('company_name')

    if not company_name:
        return jsonify({'success': False, 'error': '公司名称不能为空。'})

    # 步骤 1: 从天眼查获取数据
    company_data, error_msg = get_company_info_from_tianyancha(company_name)
    if error_msg:
        return jsonify({'success': False,
                        'error': f'分析失败：从天眼查获取“{company_name}”的信息失败。原因：{error_msg}。请检查公司名称是否正确。'})

    # 步骤 2: 使用DeepSeek进行总结
    report = summarize_info_with_deepseek(company_data)

    return jsonify({'success': True, 'report': report})

# Render 通过 gunicorn 启动时不会执行这部分
# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000)

