# -*- coding: utf-8 -*-
import os
from flask import Flask, render_template_string, request, jsonify
import requests
import json
from openai import OpenAI
from urllib.parse import quote_plus

# 初始化 Flask 应用
app = Flask(__name__)

# --- 配置部分 ---
# 从环境变量中读取API密钥和Token，这是在SAE上部署的关键
TIANYANCHA_TOKEN = os.environ.get('TIANYANCHA_TOKEN')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')

# 天眼查API的URL
TIANYANCHA_API_URL = "http://open.api.tianyancha.com/services/open/ic/baseinfoV3/2.0"

# --- HTML 模板 ---
# 将前端页面直接嵌入代码中，保持单文件结构
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>企业信息分析平台</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background-color: #f0f2f5; margin: 0; padding: 2rem; display: flex; justify-content: center; align-items: flex-start; min-height: 100vh; }
        .container { background: #fff; padding: 2.5rem; border-radius: 12px; box-shadow: 0 8px 30px rgba(0,0,0,0.1); width: 100%; max-width: 800px; transition: all 0.3s ease; }
        h1 { color: #1a2a4c; text-align: center; margin-bottom: 1rem; }
        .search-box { display: flex; gap: 1rem; margin-bottom: 2rem; }
        #companyName { flex-grow: 1; padding: 0.8rem 1rem; border: 1px solid #dcdfe6; border-radius: 8px; font-size: 1rem; transition: border-color 0.3s ease, box-shadow 0.3s ease; }
        #companyName:focus { border-color: #409eff; box-shadow: 0 0 5px rgba(64,158,255,0.2); outline: none; }
        #searchButton { padding: 0.8rem 1.5rem; background-color: #409eff; color: white; border: none; border-radius: 8px; font-size: 1rem; cursor: pointer; transition: background-color 0.3s ease, transform 0.1s ease; }
        #searchButton:hover { background-color: #66b1ff; }
        #searchButton:active { transform: scale(0.98); }
        #searchButton:disabled { background-color: #a0cfff; cursor: not-allowed; }
        .loader { display: none; text-align: center; padding: 2rem; }
        .dot-flashing { position: relative; width: 10px; height: 10px; border-radius: 5px; background-color: #409eff; color: #409eff; animation: dotFlashing 1s infinite linear alternate; animation-delay: .5s; margin: auto;}
        .dot-flashing::before, .dot-flashing::after { content: ''; display: inline-block; position: absolute; top: 0; }
        .dot-flashing::before { left: -15px; width: 10px; height: 10px; border-radius: 5px; background-color: #409eff; color: #409eff; animation: dotFlashing 1s infinite alternate; animation-delay: 0s; }
        .dot-flashing::after { left: 15px; width: 10px; height: 10px; border-radius: 5px; background-color: #409eff; color: #409eff; animation: dotFlashing 1s infinite alternate; animation-delay: 1s; }
        @keyframes dotFlashing { 0% { background-color: #409eff; } 50%, 100% { background-color: #d4e8ff; } }
        #result { margin-top: 1.5rem; border-top: 1px solid #ebeef5; padding-top: 1.5rem; }
        .error { color: #f56c6c; text-align: center; }
        /* 报告样式 */
        #report h3 { color: #303133; border-bottom: 2px solid #409eff; padding-bottom: 0.5rem; margin-top: 1.5rem; }
        #report p, #report li { color: #606266; line-height: 1.8; }
        #report strong { color: #303133; }
        #report ul { list-style-type: none; padding-left: 0; }
        #report li { background: #f9fafc; padding: 0.8rem; border-radius: 6px; margin-bottom: 0.5rem; }
        .report-section { margin-bottom: 1.5rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>企业信息分析平台</h1>
        <div class="search-box">
            <input type="text" id="companyName" placeholder="请输入完整的公司名称..." autofocus>
            <button id="searchButton">查询分析</button>
        </div>
        <div id="result"></div>
        <div class="loader" id="loader">
            <p>正在查询分析，请稍候...</p>
            <div class="dot-flashing"></div>
        </div>
    </div>

    <script>
        document.getElementById('searchButton').addEventListener('click', analyzeCompany);
        document.getElementById('companyName').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                analyzeCompany();
            }
        });

        async function analyzeCompany() {
            const companyName = document.getElementById('companyName').value.trim();
            if (!companyName) {
                document.getElementById('result').innerHTML = '<p class="error">请输入公司名称。</p>';
                return;
            }

            const searchButton = document.getElementById('searchButton');
            const loader = document.getElementById('loader');
            const resultDiv = document.getElementById('result');

            searchButton.disabled = true;
            searchButton.innerText = '查询中...';
            loader.style.display = 'block';
            resultDiv.innerHTML = '';

            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ company_name: companyName })
                });

                const data = await response.json();

                if (response.ok) {
                    resultDiv.innerHTML = data.report;
                } else {
                    resultDiv.innerHTML = `<p class="error">分析失败：${data.error || '未知错误'}</p>`;
                }
            } catch (error) {
                resultDiv.innerHTML = `<p class="error">请求失败，请检查网络连接或联系管理员。</p>`;
            } finally {
                searchButton.disabled = false;
                searchButton.innerText = '查询分析';
                loader.style.display = 'none';
            }
        }
    </script>
</body>
</html>
"""


# --- 后端逻辑 ---

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/analyze', methods=['POST'])
def analyze():
    # 检查环境变量是否配置
    if not TIANYANCHA_TOKEN or not DEEPSEEK_API_KEY:
        return jsonify({'error': '服务器环境变量未正确配置，请联系管理员。'}), 500

    data = request.get_json()
    company_name = data.get('company_name')
    if not company_name:
        return jsonify({'error': '未提供公司名称。'}), 400

    # 1. 调用天眼查API
    tyc_info = get_company_info_from_tianyancha(company_name)
    if not tyc_info:
        return jsonify({'error': f'从天眼查获取“{company_name}”的信息失败，请检查公司名称是否正确。'}), 404

    # 2. 调用DeepSeek API
    report = summarize_info_with_deepseek(tyc_info)
    if report.startswith("错误："):
        return jsonify({'error': report}), 500

    return jsonify({'report': report})


def get_company_info_from_tianyancha(company_name: str) -> dict | None:
    encoded_company_name = quote_plus(company_name)
    url = f"{TIANYANCHA_API_URL}?keyword={encoded_company_name}"
    headers = {'Authorization': TIANYANCHA_TOKEN}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        if data.get("error_code") == 0:
            return data.get("result")
        else:
            print(f"Tianyancha API Error: {data.get('reason')}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Tianyancha request failed: {e}")
        return None


def summarize_info_with_deepseek(company_info: dict) -> str:
    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        formatted_info = json.dumps(company_info, ensure_ascii=False, indent=2)

        prompt = f"""
        你是一位顶级的商业分析专家。你的任务是根据提供的企业JSON数据，生成一份专业、精炼且易于阅读的企业分析报告。

        **严格遵循以下HTML格式和要求进行输出，不要有任何额外解释：**

        **当前年份：2025年**

        <div id="report">
            <div class="report-section">
                <h3>企业速览：关键信息一目了然</h3>
                <p>
                    🏢 **公司名称**: {company_info.get('name', 'N/A')} | 
                    📆 **成立年限**: 根据成立日期（estiblishTime）和当前年份（2025）计算，例如“成立13年” | 
                    👨‍⚖️ **法定代表人**: {company_info.get('legalPersonName', 'N/A')}
                </p>
                <p>
                    💼 **注册资本**: {company_info.get('regCapital', 'N/A')} | 
                    📈 **经营状态**: {company_info.get('regStatus', 'N/A')}
                </p>
                <p>📍 **注册地址**: {company_info.get('regLocation', 'N/A')}</p>
                <p>⚖️ **行业性质**: {company_info.get('industry', 'N/A')}</p>
            </div>
            <div class="report-section">
                <h3>🏭 经营概况</h3>
                <ul>
                    <li><strong>持续经营</strong>：根据成立日期（estiblishTime）和当前年份（2025）计算运营年限，并描述其运营历史。</li>
                    <li><strong>业务聚焦</strong>：总结`businessScope`字段中的核心业务。</li>
                    <li><strong>架构精简</strong>：根据对外投资、分支机构等数据（如果为0或null），判断并说明其组织架构是否精简明晰。</li>
                </ul>
            </div>
            <div class="report-section">
                <h3>📊 经营状况</h3>
                <ul>
                    <li><strong>风险可控</strong>：总结司法案件、涉诉关系等法律风险。如果数据为0或null，明确指出“当前无公开的法律纠纷记录”。</li>
                    <li><strong>创新储备</strong>：分析知识产权（商标`tmNum`、专利`patentNum`）情况。如果为零，指出其创新储备尚未展开。</li>
                    <li><strong>⚠️ 数据缺失</strong>：检查`socialStaffNum`（社保人数）、`actualCapital`（实缴资本）等字段，如果为空或null，明确指出“关键财务信息未公示”。</li>
                </ul>
            </div>
            <div class="report-section">
                <h3>⚠️ 风险提示</h3>
                <ul>
                    <li><strong>合规记录</strong>：总结立案信息、开庭公告等风险指标。如果无，则说明“合规记录良好”。</li>
                    <li><strong>稳定性强</strong>：分析工商变更记录（`changeCount`），如果数量少或为0，则说明“工商登记信息保持稳定”。</li>
                </ul>
            </div>
            <div class="report-section">
                <h3>🔍 关注焦点预测</h3>
                <ul>
                    <li><strong>经营健康度</strong>：指出财务数据缺失可能对合作评估产生的影响。</li>
                    <li><strong>业务持续性</strong>：对长期的案件记录进行综合研判。</li>
                    <li><strong>专业资质</strong>：提示报告中未包含的核心信息，如团队构成等，有待补充。</li>
                </ul>
            </div>
            <p><small>💡 注：本报告基于公开数据生成，与实体运营可能存在差异，建议结合行业特性深入尽调。</small></p>
        </div>
        """

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一位顶级的商业分析专家，严格按照用户指令生成格式化的HTML报告。"},
                {"role": "user", "content": prompt},
            ],
            stream=False,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"DeepSeek request failed: {e}")
        return f"错误：调用DeepSeek API时发生错误: {e}"

# 注意：在SAE上部署时，不需要下面这段代码
# if __name__ == '__main__':
#     app.run(debug=True, port=5001)

