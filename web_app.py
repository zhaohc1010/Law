# -*- coding: utf-8 -*-
"""
一个基于Flask的Web应用，集成天眼查和DeepSeek API，提供网页界面来查询公司信息并生成分析报告。
此文件用于部署到 LeanCloud 等 PaaS 平台。
"""

import os
import requests
import json
from openai import OpenAI
from urllib.parse import quote_plus
from flask import Flask, request, jsonify, render_template_string

# --- Flask 应用初始化 ---
app = Flask(__name__)

# --- 配置部分 ---
# 从 LeanCloud 的环境变量中读取密钥，确保安全
TIANYANCHA_TOKEN = os.environ.get('TIANYANCHA_TOKEN')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
TIANYANCHA_API_URL = "http://open.api.tianyancha.com/services/open/ic/baseinfoV3/2.0"

# --- 前端HTML模板 ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>企业信息智能分析平台</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background-color: #f4f7f9; color: #333; margin: 0; padding: 20px; display: flex; justify-content: center; }
        .container { width: 100%; max-width: 800px; background-color: #fff; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); padding: 30px; }
        h1 { color: #1a2a4d; text-align: center; margin-bottom: 25px; }
        #company-form { display: flex; gap: 10px; margin-bottom: 20px; }
        #company-name { flex-grow: 1; padding: 12px; border: 1px solid #ccc; border-radius: 6px; font-size: 16px; }
        #company-form button { padding: 12px 20px; background-color: #007bff; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; transition: background-color 0.3s; }
        #company-form button:hover { background-color: #0056b3; }
        #loader { text-align: center; padding: 20px; font-size: 18px; color: #555; display: none; }
        .result-section { margin-top: 25px; border-top: 1px solid #eee; padding-top: 20px; }
        .result-section h2 { color: #1a2a4d; border-bottom: 2px solid #007bff; padding-bottom: 8px; }
        pre { background-color: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 6px; white-space: pre-wrap; word-wrap: break-word; font-family: 'Courier New', Courier, monospace; }
        .report-content { line-height: 1.8; font-size: 16px; }
        .report-content h3 { margin-top: 20px; }
        .error { color: #d93025; font-weight: bold; text-align: center; padding: 15px; background-color: #fbeae9; border-radius: 6px;}
    </style>
</head>
<body>
    <div class="container">
        <h1>企业信息智能分析平台</h1>
        <form id="company-form">
            <input type="text" id="company-name" placeholder="请输入完整的公司名称" required>
            <button type="submit">立即分析</button>
        </form>
        <div id="loader">
            <p>🔍 正在获取数据并调用AI分析，请稍候...</p>
        </div>
        <div id="result-container"></div>
    </div>

    <script>
        document.getElementById('company-form').addEventListener('submit', async function(event) {
            event.preventDefault();
            const companyName = document.getElementById('company-name').value;
            const loader = document.getElementById('loader');
            const resultContainer = document.getElementById('result-container');

            loader.style.display = 'block';
            resultContainer.innerHTML = '';

            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ company_name: companyName }),
                });

                const data = await response.json();

                if (response.ok) {
                    let output = `
                        <div class="result-section">
                            <h2>天眼查原始数据</h2>
                            <pre><code>${JSON.stringify(data.raw_data, null, 2)}</code></pre>
                        </div>
                        <div class="result-section">
                            <h2>公司信息分析报告</h2>
                            <div class="report-content">${data.report.replace(/\\n/g, '<br>').replace(/### (.*?)\\n/g, '<h3>$1</h3>')}</div>
                        </div>
                    `;
                    resultContainer.innerHTML = output;
                } else {
                    resultContainer.innerHTML = `<div class="error">错误: ${data.error}</div>`;
                }
            } catch (error) {
                resultContainer.innerHTML = `<div class="error">请求失败，请检查网络连接或服务器状态。</div>`;
            } finally {
                loader.style.display = 'none';
            }
        });
    </script>
</body>
</html>
"""


# --- 后端API逻辑 ---

def get_company_info_from_tianyancha(company_name: str) -> dict | None:
    if not TIANYANCHA_TOKEN:
        print("错误：未找到天眼查Token。")
        return None
    encoded_company_name = quote_plus(company_name)
    url = f"{TIANYANCHA_API_URL}?keyword={encoded_company_name}"
    headers = {'Authorization': TIANYANCHA_TOKEN}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("error_code") == 0:
            return data.get("result")
        else:
            print(f"天眼查API错误: {data.get('reason', '未知错误')}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"请求天眼查API时发生网络错误: {e}")
        return None
    except json.JSONDecodeError:
        print("解析天眼查返回的JSON数据失败。")
        return None


def summarize_info_with_deepseek(company_info: dict) -> str:
    if not DEEPSEEK_API_KEY:
        return "错误：未找到DeepSeek API密钥。"
    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        formatted_info = json.dumps(company_info, ensure_ascii=False, indent=2)
        prompt = f"""
        你是一位顶级的商业分析专家。你的任务是根据提供的企业JSON数据，生成一份专业、精炼且易于阅读的企业分析报告。
        **严格遵循以下格式和要求进行输出，不要有任何额外解释：**
        **当前年份：2025年**

        ### 企业速览：关键信息一目了然
        🏢 [公司名] | 📆 成立[年数]年 | 👨‍⚖️ 法定代表人：[法人名]
        💼 注册资本：[注册资本] | 经营状态：[经营状态]
        📍 注册地址：[注册地址]
        ⚖️ 行业性质：[行业]
        ---
        我们为您精选了以下值得关注的核心内容
        ---
        ### 🏭 经营概况
        - **📈 持续经营**：根据成立日期（estiblishTime）和当前年份（2025）计算运营年限，并描述其运营历史。
        - **🔧 业务聚焦**：总结`businessScope`字段中的核心业务。
        - **📊 架构精简**：根据对外投资、分支机构等数据（如果为0或null），判断并说明其组织架构是否精简明晰。

        ### 📊 经营状况
        - **✅ 风险可控**：总结司法案件、涉诉关系等法律风险。如果数据为0或null，明确指出“当前无公开的法律纠纷记录”。
        - **📉 创新储备**：分析知识产权（商标`tmNum`、专利`patentNum`）情况。如果为零，指出其创新储备尚未展开。
        - **⚠️ 数据缺失**：检查`socialStaffNum`（社保人数）、`actualCapital`（实缴资本）等字段，如果为空或null，明确指出“关键财务信息未公示”。

        **现在，请根据以下公司JSON数据开始分析:**
        {formatted_info}
        """
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一位顶级的商业分析专家，严格按照用户指令生成格式化的报告。"},
                {"role": "user", "content": prompt},
            ],
            stream=False, max_tokens=1500, temperature=0.5
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"调用DeepSeek API时发生错误: {e}"


# --- Flask路由 ---

@app.route('/')
def index():
    """渲染主页面"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/analyze', methods=['POST'])
def analyze_company():
    """处理分析请求"""
    if not TIANYANCHA_TOKEN or not DEEPSEEK_API_KEY:
        return jsonify({'error': '服务器未配置API密钥，请联系管理员。'}), 500

    data = request.get_json()
    if not data or 'company_name' not in data:
        return jsonify({'error': '请求中缺少公司名称'}), 400

    company_name = data['company_name'].strip()
    if not company_name:
        return jsonify({'error': '公司名称不能为空'}), 400

    company_data = get_company_info_from_tianyancha(company_name)
    if not company_data:
        return jsonify({'error': f"未能从天眼查获取到'{company_name}'的相关信息，请检查公司名称是否正确。"}), 404

    summary_report = summarize_info_with_deepseek(company_data)

    return jsonify({
        'raw_data': company_data,
        'report': summary_report
    })


# --- LeanCloud 启动入口 ---
# LeanCloud 会通过 PORT 环境变量告诉我们应该监听哪个端口
if __name__ == '__main__':
    port = int(os.environ.get('LEANCLOUD_APP_PORT', 5000))
    app.run(host='0.0.0.0', port=port)

