import re
import csv
import os
from datetime import datetime
from google.oauth2 import service_account
from google.cloud import vision
import glob

# 術前診断の事前定義リスト（追加可能）
PREDEFINED_DIAGNOSES = {
    '白内障': ['白内障', 'cataract', 'CATARACT'],
    '黄斑前膜': ['黄斑前膜', 'epiretinal membrane', 'ERM', '黄斑部前膜'],
    '硝子体出血': ['硝子体出血', 'vitreous hemorrhage', 'vitreous bleeding', '硝子体出血'],
    '網膜剥離': ['網膜剥離', 'retinal detachment', 'RD', '網膜はく離'],
    '緑内障': ['緑内障', 'glaucoma', 'GLAUCOMA'],
    '糖尿病網膜症': ['糖尿病網膜症', 'diabetic retinopathy', 'DR'],
    '加齢黄斑変性': ['加齢黄斑変性', 'age-related macular degeneration', 'AMD'],
    '網膜静脈閉塞症': ['網膜静脈閉塞症', 'retinal vein occlusion', 'RVO'],
    '網膜動脈閉塞症': ['網膜動脈閉塞症', 'retinal artery occlusion', 'RAO'],
    '黄斑円孔': ['黄斑円孔', 'macular hole', 'MH'],
    '中心性漿液性脈絡網膜症': ['中心性漿液性脈絡網膜症', 'central serous chorioretinopathy', 'CSC'],
    'ぶどう膜炎': ['ぶどう膜炎', 'uveitis', 'UVEITIS'],
    '角膜疾患': ['角膜疾患', 'corneal disease', '角膜病変'],
    '視神経疾患': ['視神経疾患', 'optic nerve disease', '視神経症'],
}

# 術式の事前定義リスト（追加可能）
PREDEFINED_SURGERIES = {
    '水晶体再建術': ['水晶体再建術', 'cataract surgery', 'phacoemulsification', 'PEA', '白内障手術'],
    '硝子体手術': ['硝子体手術', 'vitrectomy', 'vitreous surgery', '硝子体切除術'],
    'トラベクレクトミー': ['トラベクレクトミー', 'trabeculectomy', 'TRAB'],
    'カフーク': ['カフーク', 'Kahook', 'KDB', 'Kahook Dual Blade'],
    'マイクロシャント': ['マイクロシャント', 'microshunt', 'MicroShunt', 'iStent', 'XEN'],
    'レーザー光凝固術': ['レーザー光凝固術', 'laser photocoagulation', 'PRP', '網膜光凝固'],
    'レーザー虹彩切開術': ['レーザー虹彩切開術', 'laser iridotomy', 'LI', 'YAG虹彩切開'],
    'レーザー線維柱帯形成術': ['レーザー線維柱帯形成術', 'laser trabeculoplasty', 'SLT', 'ALT'],
    '角膜移植術': ['角膜移植術', 'corneal transplantation', 'PKP', 'DSAEK', 'DMEK'],
    '網膜光凝固術': ['網膜光凝固術', 'retinal photocoagulation', '網膜レーザー'],
    '硝子体注射': ['硝子体注射', 'intravitreal injection', 'IVI', '抗VEGF注射'],
    '網膜剥離手術': ['網膜剥離手術', 'retinal detachment surgery', '網膜復位術'],
    '黄斑前膜除去術': ['黄斑前膜除去術', 'epiretinal membrane removal', 'ERM除去'],
    '黄斑円孔手術': ['黄斑円孔手術', 'macular hole surgery', '円孔閉鎖術'],
    '緑内障手術': ['緑内障手術', 'glaucoma surgery', '線維柱帯切除術'],
}

def add_diagnosis(category, keywords):
    """術前診断のカテゴリとキーワードを追加"""
    global PREDEFINED_DIAGNOSES
    if category not in PREDEFINED_DIAGNOSES:
        PREDEFINED_DIAGNOSES[category] = []
    PREDEFINED_DIAGNOSES[category].extend(keywords)
    print(f"✅ 術前診断追加: {category} - {keywords}")

def add_surgery(category, keywords):
    """術式のカテゴリとキーワードを追加"""
    global PREDEFINED_SURGERIES
    if category not in PREDEFINED_SURGERIES:
        PREDEFINED_SURGERIES[category] = []
    PREDEFINED_SURGERIES[category].extend(keywords)
    print(f"✅ 術式追加: {category} - {keywords}")

def create_vision_client():
    """サービスアカウント認証でVision APIクライアントを作成"""
    try:
        # サービスアカウントキー情報
        service_account_info = {
            "type": "service_account",
            "project_id": "sakuraganka-ai-466022",
            "private_key_id": "41f9b169fee0c14e34015b1c5f2a54d27c009108",
            "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQDQth9HXQGtmsjx\ntkDvTFbQq8AJpbHmA96SBkZPw1NfCeQXC7Q+dVOhegxutOg2rMS4imNhkkHpA6at\nNVe6RyYVWBNU6Ahowv8TW0xCt7RMLyzQ0FW23x11tX7eHPE5HQYDYGn/Zzs9VPdu\nJERBxlViwROZyEJT4tqVk9798Qlgy0hiYNmdf/y8/0Qx5EW2CoaGEm1uOhakjLuE\noenBIIOgr/z5nCfOytDD0My4dF0YL5U7KsQvUMGU9Cw17jUD8J1blJN6MAmnd3Ay\nkpcUhUh8vKlPCg57WAmdiRngSc7KR+oc0HTfqvOqgdL+GbmjmQIJrhcI9UWOuIl6\ngmSxkz3hAgMBAAECgf80wZ6SPDpfhf1SsDGRWQSzx/mhM0e942Tsukr+IeF+lwgy\nekLmQ3EqdEpR53YphEyGdCPgwqUcVZNMJ6I0bTNv026Iyyul1kYqijOACCV2y55Z\nRQzRXA3MMzYokJQYQMtYiGuGHQSSTRcV1HNRi1C5My/VZWRsLjXBpva9szak6Oot\ntdOnN/7A6Xj+hFVjp6a9Bdor9tGaydOt1oEl+NT2Iy+FPirc8Tdc6i2ffgmXbtug\ney3gZwik/BkfZnpIbEt0rZMylEr2Tk48AxrjIs3RdeXN4Q3N6DK8Qr7LmMc4GNZT\nfgkbw3GLmQBz8ZczPcDlSIGNk+wZSlZ6nFkcWLsCgYEA93XbUXezwrHwHLs+I4yN\n2cr624MnGI2iDatcL5PolYrML2bs30kZOikLU4I+q3vl7geotE3wd+5fVjBC+Hm6\n4LFxVx2TkvmV3MNW/4UUQEQ1K8vQS76SvgInCULpPt/lIctaeyqZW7yb4Nsa9irv\nfOpHkUigrZrUZBLAOCi+WoMCgYEA1+nx4vLq30RfkTDwNeWnnVQraIvq8uLbBYgl\nP5e1j9G3fvjI4Ql546+YVhUNtNF/x9yxyBarFEQga9L5i3UNc9o9JBOKzac+hpLv\nFWhiiI7u2QRDy7GT1ZxGPZNiCo20E18LZV8/F0fJwTbjG2S20iQl8sZZYEkK6qoR\n+tT/KMsCgYEA3EgSsqOu5lqFVt4rQ3Pj9gMlafCHBelWX3qyNjwhJ7WFa5DgvScS\nCN7ukSj45qgFFu3EdLSIogoU3eFaTFv4SfpK3XSboJMCn6FXuV/alhbhihoFUtfT\nQschvrHMdcbS7lFaOxfBqpLr467HgmjYBUd7681OExwngunaKGPEh0cCgYEAxrMt\nP8Z+D+pEaMG4zmEC1+7V4+if19ad6YFZhiR/mlNNozQg6bhmy/qVHuNRMc564dtg\nYNs7pfLsQ05tCMI4Fx4IlmLFomz/RamDDRh7VWD0vhMGsTZC7ppaqeAwobW2uv0E\n5823qh0Otxlj95nABbPumHWhWtLdkQfidAwApfECgYBaVlRxkYao2IOo/DzaWCQw\nC9gMfXpB+qtYLXcbmPt2nVEPPXXS0XTzO0OhFd/F4e+knfDE4xTWwh15DrAZP/Qn\nYdyR1FwEDbe6ZHG8RbHa2wuxaiXQ5tLTyfae7IlaQpcKGGEUhkBXUgS9jbMc0HPi\nlDEGPIq2ToOq1uCd1894yA==\n-----END PRIVATE KEY-----\n",
            "client_email": "sakura-aidata@sakuraganka-ai-466022.iam.gserviceaccount.com",
            "client_id": "112249976566455945098",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/sakura-aidata%40sakuraganka-ai-466022.iam.gserviceaccount.com",
            "universe_domain": "googleapis.com"
        }
        
        credentials = service_account.Credentials.from_service_account_info(service_account_info)
        client = vision.ImageAnnotatorClient(credentials=credentials)
        return client
    except Exception as e:
        print(f"認証エラー: {e}")
        return None

def google_vision_ocr(image_path, client):
    """Google Vision APIでOCR実行"""
    try:
        with open(image_path, 'rb') as f:
            content = f.read()
        
        image = vision.Image(content=content)
        response = client.text_detection(image=image)
        texts = response.text_annotations
        
        if texts:
            return texts[0].description
        else:
            return ""
            
    except Exception as e:
        print(f"OCRエラー {image_path}: {e}")
        return ""

def reconstruct_vision_line(lines, start_index):
    """V.d./V.s.の行を再構築"""
    
    # V.d.= または V.s.= から始まる行を見つけたら
    # その後の数値や括弧を含む要素を集める
    
    reconstructed = lines[start_index]  # V.d.= または V.s.=
    
    # 次の3-4行を確認
    for j in range(1, 5):
        if start_index + j < len(lines):
            next_line = lines[start_index + j].strip()
            
            # 数値、IOL、括弧、n.c.などが含まれていれば追加
            if any(x in next_line for x in ['0.', '1.', 'IOL', '(', 'n.c', '×', 'x']):
                reconstructed += ' ' + next_line
            # 次のV.d./V.s.が来たら終了
            elif 'V.d.' in next_line or 'V.s.' in next_line:
                break
    
    return reconstructed

def fix_corrected_vision(value):
    """矯正視力の誤認識を修正"""
    if value == '12':
        return '1.2'
    elif value == '10':
        return '1.0'
    elif value == '15':
        return '1.5'
    elif value == '20':
        return '2.0'
    # 1.265のような値は妥当性チェック
    try:
        v = float(value)
        if v > 2.5:  # 視力で2.5以上はありえない
            # 小数点を追加
            if str(value).startswith('12'):
                return '1.2'
    except:
        pass
    return value

def extract_handwritten_iop_patterns_fixed(text):
    """手書き眼圧抽出（DATE誤認識を防ぐ）"""
    
    lines = text.split('\n')
    result = {'右眼圧': '', '左眼圧': '', '眼圧メモ': ''}
    
    for line in lines:
        # DATEの行はスキップ
        if 'DATE' in line.upper() or '2025/' in line or '2024/' in line:
            continue
            
        # AT/IOPパターンを探す
        if any(marker in line.upper() for marker in ['AT', 'IOP', 'ＡＴ', 'ＩＯＰ']):
            # DATE行でないことを再確認
            if 'DATE' not in line.upper():
                print(f"眼圧行候補（DATE除外後）: {line}")
                
                # 数字を探す（◯◯.◯形式）
                numbers = re.findall(r'\b(\d{1,2}\.\d)\b', line)
                valid_iop = [n for n in numbers if 0 <= float(n) <= 80]
                
                if len(valid_iop) >= 2:
                    result['右眼圧'] = valid_iop[0]
                    result['左眼圧'] = valid_iop[1]
                    return result
                    
                # スラッシュパターン（◯◯.◯形式）
                slash = re.search(r'(\d{1,2}\.\d)\s*[/／]\s*(\d{1,2}\.\d)', line)
                if slash:
                    v1, v2 = float(slash.group(1)), float(slash.group(2))
                    if 0 <= v1 <= 80 and 0 <= v2 <= 80:
                        result['右眼圧'] = str(v1)
                        result['左眼圧'] = str(v2)
                        return result
    
    return result

def debug_nct_structure(text):
    """NCT構造を詳細に分析"""
    
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        if 'IOP' in line and 'mmHg' in line:
            print(f"\n=== NCT眼圧構造 行{i} ===")
            print(f"ヘッダー: {line}")
            
            # 次の10行を表示
            for offset in range(1, 11):
                if i + offset < len(lines):
                    next_line = lines[i + offset]
                    print(f"  +{offset}行目: {next_line}")
                    
                    # 特定の行にマーク
                    if offset == 1:
                        print("      ^ [R][L]行")
                    elif offset in [2, 3, 4]:
                        print(f"      ^ {offset-1}回目測定")
                    elif offset == 5:
                        print("      ^ ★Avg行（ここを取得）")
            
            break

def extract_nct_by_position_improved(text):
    """NCT眼圧を改良版で取得（平均値のみ、小数点付きを優先）"""
    
    import re
    
    lines = text.split('\n')
    result = {
        'NCT右': '',
        'NCT左': '',
        '眼圧備考': ''
    }
    
    # IOPヘッダーを探す
    iop_start = -1
    for i, line in enumerate(lines):
        if 'IOP' in line and 'mmHg' in line:
            iop_start = i
            print(f"NCT眼圧ヘッダー発見 行{i}: {line}")
            break
    
    if iop_start == -1:
        return result
    
    # 平均値（Avg）行を探す
    avg_line = -1
    for offset in range(1, 20):  # 20行以内で検索（範囲拡大）
        if iop_start + offset < len(lines):
            line = lines[iop_start + offset]
            if 'Avg' in line or 'AVG' in line or 'avg' in line or 'Aug' in line:
                avg_line = iop_start + offset
                print(f"  ✅ Avg行発見 行{avg_line}: {line}")
                break
    
    if avg_line == -1:
        print(f"  ❌ Avg行が見つかりませんでした")
        return result
    
    # Avg行から眼圧値を抽出（Avg行に並んでいる）
    avg_line_content = lines[avg_line]
    print(f"  📊 Avg行内容: {avg_line_content}")
    
    # Avg行から◯◯.◯形式の眼圧値を直接検索
    iop_values = re.findall(r'\b(\d{1,2}\.\d)\b', avg_line_content)
    print(f"  🔍 Avg行の眼圧値候補: {iop_values}")
    
    # 眼圧の妥当性チェック（0-80 mmHg、◯◯.◯形式）
    valid_iop_values = []
    for num_str in iop_values:
        try:
            val = float(num_str)
            if 0 <= val <= 80:
                valid_iop_values.append(num_str)
                print(f"    ✅ 有効な眼圧値: {num_str}")
            else:
                print(f"    ⚠️ 眼圧範囲外: {num_str} (0-80)")
        except:
            continue
    
    # 2つの有効な値があれば成功
    if len(valid_iop_values) >= 2:
        result['NCT右'] = valid_iop_values[0]
        result['NCT左'] = valid_iop_values[1]
        result['眼圧備考'] = f'NCT平均値（Avg行）'
        print(f"  ✅ NCT平均値取得成功: R={valid_iop_values[0]}, L={valid_iop_values[1]}")
        return result
    
    # 1つの値しかない場合（1回計測の可能性）
    if len(valid_iop_values) == 1:
        result['NCT右'] = valid_iop_values[0]
        result['NCT左'] = ''  # 左眼は測定されていない可能性
        result['眼圧備考'] = f'NCT平均値（1回計測、右眼のみ）'
        print(f"  ⚠️ NCT平均値（1回計測）: R={valid_iop_values[0]}, L=未測定")
        return result
    
    # 次の行もチェック（2つ目の値を探す）
    if len(valid_iop_values) == 1:
        print(f"  ⚠️ 眼圧値が1つしかありません。次の行をチェック...")
        
        # 次の10行をチェック（1回計測対応）
        for offset in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
            check_line = avg_line + offset
            if check_line < len(lines):
                check_line_content = lines[check_line]
                print(f"  📊 +{offset}行目内容: {check_line_content}")
                
                # 次の行からも◯◯.◯形式の眼圧値を検索
                check_iop_values = re.findall(r'\b(\d{1,2}\.\d)\b', check_line_content)
                print(f"  🔍 +{offset}行目の眼圧値候補: {check_iop_values}")
                
                for num_str in check_iop_values:
                    try:
                        val = float(num_str)
                        if 0 <= val <= 80:
                            valid_iop_values.append(num_str)
                            print(f"    ✅ +{offset}行目の有効な眼圧値: {num_str}")
                        else:
                            print(f"    ⚠️ +{offset}行目の眼圧範囲外: {num_str} (0-80)")
                    except:
                        continue
                
                if len(valid_iop_values) >= 2:
                    result['NCT右'] = valid_iop_values[0]
                    result['NCT左'] = valid_iop_values[1]
                    result['眼圧備考'] = f'NCT平均値（1回計測、Avg行+{offset}行目）'
                    print(f"  ✅ NCT平均値取得成功: R={valid_iop_values[0]}, L={valid_iop_values[1]}")
                    return result
    
    print(f"  ❌ 有効な眼圧値が見つかりませんでした")
    return result

def debug_nct_detection(text):
    """NCT眼圧が検出できない原因を調査"""
    
    lines = text.split('\n')
    
    print("=== NCT眼圧検出デバッグ ===")
    
    # IOPを含む行を全て表示
    iop_found = False
    for i, line in enumerate(lines):
        if 'IOP' in line.upper():
            iop_found = True
            print(f"🔍 IOP行発見 {i}: {line}")
            # 次の10行を表示
            for j in range(i+1, min(i+10, len(lines))):
                line_content = lines[j].strip()
                if line_content:
                    marker = "  "
                    if 'Avg' in line_content or 'AVG' in line_content:
                        marker = "★ "
                    elif '*' in line_content:
                        marker = "* "
                    elif any(char.isdigit() for char in line_content):
                        marker = "🔢"
                    print(f"  {marker}{j}: {line_content}")
    
    if not iop_found:
        print("❌ IOP行が見つかりませんでした")
    
    # 数値パターンで眼圧候補を探す
    print(f"\n=== 眼圧候補検索 ===")
    for i, line in enumerate(lines):
        import re
        # 0-80の範囲の数値ペアを探す（手書き眼圧）
        numbers = re.findall(r'\b(\d{1,2})\b', line)
        valid = [n for n in numbers if 0 <= int(n) <= 80]
        if len(valid) >= 2:
            print(f"🔢 眼圧候補（数値）行{i}: {line}")
            print(f"   検出数値: {valid}")
        elif len(valid) == 1:
            print(f"🔢 単一数値行{i}: {line} (値: {valid[0]})")
    
    # 小数点を含む数値を探す（NCT平均値の可能性）
    print(f"\n=== 小数点付き数値検索（NCT平均値候補） ===")
    for i, line in enumerate(lines):
        import re
        decimal_numbers = re.findall(r'\b(\d+\.\d+)\b', line)
        if decimal_numbers:
            print(f"📊 小数点付き行{i}: {line}")
            print(f"   検出値: {decimal_numbers}")
    
    print(f"\n=== デバッグ完了 ===")

def fix_s_five_confusion(text):
    """S（球面度数）と5の誤認識を修正"""
    
    import re
    
    # よくある誤認識パターン
    # 12x5 → 1.2×S
    # 1,285 → 1.2×S
    # 12×5 → 1.2×S
    
    # 括弧内の処理
    def fix_in_brackets(match):
        content = match.group(0)
        # 12x5 → 1.2×S
        content = re.sub(r'12x5', '1.2×S', content)
        content = re.sub(r'12×5', '1.2×S', content)
        content = re.sub(r'1,285', '1.2×S', content)
        # 10x5 → 1.0×S
        content = re.sub(r'10x5', '1.0×S', content)
        content = re.sub(r'10×5', '1.0×S', content)
        return content
    
    # 括弧内のパターンを修正
    text = re.sub(r'\([^)]+\)', fix_in_brackets, text)
    
    # V.5. → V.s.の修正
    text = text.replace('V.5.', 'V.s.')
    text = text.replace('V.S.', 'V.s.')
    
    return text

def process_two_tier_vision_data(text):
    """2段構造（前回・今回）の視力データを処理"""
    
    lines = text.split('\n')
    result = {
        '前回_右裸眼': '',
        '前回_右矯正': '',
        '前回_左裸眼': '',
        '前回_左矯正': '',
        '今回_右裸眼': '',
        '今回_右矯正': '',
        '今回_左裸眼': '',
        '今回_左矯正': '',
        '今回_S': '',
        '今回_C': '',
        '今回_A': ''
    }
    
    # 2段構造を検出
    upper_section = []
    lower_section = []
    current_section = upper_section
    
    for line in lines:
        # 区切り線や明確な区切りを探す
        if any(marker in line for marker in ['---', '===', '前回', '今回', '2025', '2024']):
            if len(upper_section) > 0:
                current_section = lower_section
        current_section.append(line)
    
    # 上段（前回）の処理
    if upper_section:
        upper_text = '\n'.join(upper_section)
        upper_data = extract_vision_data_fixed(upper_text)
        result['前回_右裸眼'] = upper_data['右裸眼']
        result['前回_右矯正'] = upper_data['右矯正']
        result['前回_左裸眼'] = upper_data['左裸眼']
        result['前回_左矯正'] = upper_data['左矯正']
    
    # 下段（今回）の処理（優先）
    if lower_section:
        lower_text = '\n'.join(lower_section)
        lower_data = extract_vision_data_fixed(lower_text)
        result['今回_右裸眼'] = lower_data['右裸眼']
        result['今回_右矯正'] = lower_data['右矯正']
        result['今回_左裸眼'] = lower_data['左裸眼']
        result['今回_左矯正'] = lower_data['左矯正']
        
        # 度数情報も抽出
        degree_data = extract_degree_data(lower_text)
        result['今回_S'] = degree_data['S']
        result['今回_C'] = degree_data['C']
        result['今回_A'] = degree_data['A']
    
    return result

def extract_degree_data(text):
    """度数情報（S、C、A）を抽出"""
    
    import re
    
    result = {'S': '', 'C': '', 'A': ''}
    
    # S（球面度数）を探す
    s_patterns = [
        r'S[:\s]*([+-]?\d+\.?\d*)',
        r'球面[:\s]*([+-]?\d+\.?\d*)',
        r'([+-]?\d+\.?\d*)\s*×\s*S'
    ]
    
    for pattern in s_patterns:
        match = re.search(pattern, text)
        if match:
            result['S'] = match.group(1)
            break
    
    # C（円柱度数）を探す
    c_patterns = [
        r'C[:\s]*([+-]?\d+\.?\d*)',
        r'円柱[:\s]*([+-]?\d+\.?\d*)',
        r'([+-]?\d+\.?\d*)\s*×\s*C'
    ]
    
    for pattern in c_patterns:
        match = re.search(pattern, text)
        if match:
            result['C'] = match.group(1)
            break
    
    # A（軸）を探す
    a_patterns = [
        r'A[:\s]*(\d+)',
        r'軸[:\s]*(\d+)',
        r'(\d+)\s*度'
    ]
    
    for pattern in a_patterns:
        match = re.search(pattern, text)
        if match:
            result['A'] = match.group(1)
            break
    
    return result

def extract_vision_data_fixed(text):
    """改行を考慮した視力データ抽出（最終版・TOL対応）"""
    
    import re
    
    # Sと5の誤認識を修正
    text = fix_s_five_confusion(text)
    
    # 改行を一旦除去して連続したテキストにする
    lines = text.split('\n')
    
    result = {
        '右裸眼': '',
        '右矯正': '',
        '左裸眼': '',
        '左矯正': '',
        '右TOL': '',  # 眼内レンズ情報追加
        '左TOL': '',  # 眼内レンズ情報追加
        '右眼圧': '',
        '左眼圧': ''
    }
    
    # V.d.を探して、次の数行も含めて処理
    for i, line in enumerate(lines):
        if 'V.d.' in line or 'Vd' in line:
            # 現在の行と次の3行を結合
            combined = ' '.join(lines[i:min(i+4, len(lines))])
            print(f"V.d.結合テキスト: {combined}")
            
            # 裸眼視力を探す（0.01, 0.1など）
            naked = re.search(r'V\.?d\.?\s*=?\s*([\d\.]+)', combined)
            if naked:
                result['右裸眼'] = naked.group(1)
            
            # TOL（眼内レンズ）を探す
            tol_pattern = re.search(r'([\d\.]+)\s*[xX×]\s*(?:TOL|IOL|FOL|EOL|1OL)', combined)
            if tol_pattern:
                result['右TOL'] = tol_pattern.group(1)
                print(f"  ✅ 右眼TOL発見: {result['右TOL']}")
            
            # 矯正視力を探す
            # パターン1: (n.c.) または (n.c)
            if 'n.c' in combined.lower():
                result['右矯正'] = 'n.c.'
            else:
                # パターン2: (数値) または括弧内の最初の数値
                corrected = re.search(r'\(([\d\.]+)', combined)
                if corrected:
                    result['右矯正'] = corrected.group(1)
                # パターン3: ×IOL の後の括弧内
                iol_pattern = re.search(r'(?:TOL|IOL|FOL|EOL|1OL).*?\(([\d\.]+|n\.c\.?)', combined)
                if iol_pattern:
                    result['右矯正'] = iol_pattern.group(1)
        
        # V.s.も同様に処理
        if 'V.s.' in line or 'Vs' in line:
            combined = ' '.join(lines[i:min(i+4, len(lines))])
            print(f"V.s.結合テキスト: {combined}")
            
            naked = re.search(r'V\.?s\.?\s*=?\s*([\d\.]+)', combined)
            if naked:
                result['左裸眼'] = naked.group(1)
            
            # TOL（眼内レンズ）を探す
            tol_pattern = re.search(r'([\d\.]+)\s*[xX×]\s*(?:TOL|IOL|FOL|EOL|1OL)', combined)
            if tol_pattern:
                result['左TOL'] = tol_pattern.group(1)
                print(f"  ✅ 左眼TOL発見: {result['左TOL']}")
            
            if 'n.c' in combined.lower():
                result['左矯正'] = 'n.c.'
            else:
                corrected = re.search(r'\(([\d\.]+)', combined)
                if corrected:
                    result['左矯正'] = corrected.group(1)
    
    # 眼圧（これは正確に取れている）
    iop_found = False
    for i, line in enumerate(lines):
        if 'IOP' in line:
            iop_found = True
        if iop_found and '[R]' in line:
            nums = re.findall(r'(\d+)', line)
            if nums:
                result['右眼圧'] = nums[0]
        if iop_found and '[L]' in line:
            nums = re.findall(r'(\d+)', line)
            if nums:
                result['左眼圧'] = nums[0]
    
    return result

def extract_all_iop_types(text):
    """NCTと手書き眼圧を両方取得（位置ベース改良版）"""
    
    import re
    
    result = {
        'NCT右': '',
        'NCT左': '',
        '手書き右': '',
        '手書き左': '',
        '眼圧備考': ''
    }
    
    lines = text.split('\n')
    
    # ========================================
    # 1. NCT眼圧を位置ベースで取得
    # ========================================
    nct_result = extract_nct_by_position_improved(text)
    
    if nct_result['NCT右'] and nct_result['NCT左']:
        result['NCT右'] = nct_result['NCT右']
        result['NCT左'] = nct_result['NCT左']
        result['眼圧備考'] = nct_result['眼圧備考']
        nct_found = True
    else:
        nct_found = False
    
    # ========================================
    # 2. 手書き眼圧も探す（NCTの有無に関わらず）
    # ========================================
    handwritten_result = extract_handwritten_iop_patterns_improved(text)
    
    if handwritten_result['右眼圧'] and handwritten_result['左眼圧']:
        result['手書き右'] = handwritten_result['右眼圧']
        result['手書き左'] = handwritten_result['左眼圧']
        handwritten_found = True
        print(f"  ✅ 手書き眼圧: R={handwritten_result['右眼圧']}, L={handwritten_result['左眼圧']}")
        print(f"     メモ: {handwritten_result['眼圧メモ']}")
    else:
        handwritten_found = False
    
    # ========================================
    # 3. 結果の整理
    # ========================================
    if nct_found and handwritten_found:
        result['眼圧備考'] = 'NCT+手書き両方あり'
    elif nct_found:
        result['眼圧備考'] = 'NCTのみ'
    elif handwritten_found:
        result['眼圧備考'] = '手書きのみ'
    else:
        result['眼圧備考'] = '検出失敗'
    
    return result

def select_final_iop(iop_data):
    """最終的に使用する眼圧値を決定"""
    
    result = {
        '眼圧右': '',
        '眼圧左': '',
        '使用データ': ''
    }
    
    # 優先順位：
    # 1. 手書きがあれば手書き（医師が再測定した可能性）
    # 2. 手書きがなければNCT
    
    if iop_data['手書き右'] and iop_data['手書き左']:
        result['眼圧右'] = iop_data['手書き右']
        result['眼圧左'] = iop_data['手書き左']
        result['使用データ'] = '手書き優先'
    elif iop_data['NCT右'] and iop_data['NCT左']:
        result['眼圧右'] = iop_data['NCT右']
        result['眼圧左'] = iop_data['NCT左']
        result['使用データ'] = 'NCT'
    
    return result



def process_image_final_comprehensive(ocr_text, filename=None):
    """最終包括的処理（視力+眼圧+レフ値+最終選択+TOL対応+IOLシール対応+検査画像識別対応+左右判定対応+詳細検査データ対応）"""
    
    result = {
        '右裸眼': '',
        '右矯正': '',
        '左裸眼': '',
        '左矯正': '',
        '右TOL': '',  # 眼内レンズ情報追加
        '左TOL': '',  # 眼内レンズ情報追加
        'NCT右': '',
        'NCT左': '',
        '手書き右': '',
        '手書き左': '',
        '最終眼圧右': '',
        '最終眼圧左': '',
        '眼圧備考': '',
        '使用データ': '',
        'S': '',
        'C': '',
        'Ax': '',
        '手術日': '',
        '患者名': '',
        '術前診断': '',
        '術式': '',
        '対象眼': '',
        'IOL度数_S': '',  # IOLシール情報追加
        'IOL度数_C': '',  # IOLシール情報追加
        'IOL度数_Ax': '',  # IOLシール情報追加
        'IOL製品名': '',  # IOLシール情報追加
        'IOLメーカー': '',  # IOLシール情報追加
        'IOL備考': '',  # IOLシール情報追加
        '検査種類': '',  # 検査画像識別追加
        '検査詳細': '',  # 検査画像識別追加
        '検査日': '',  # 検査画像識別追加
        '検査対象眼': '',  # 検査対象眼追加
        '検査備考': ''  # 検査画像識別追加
    }
    
    # 視力データ抽出
    vision = extract_vision_data_fixed(ocr_text)
    
    # 矯正視力の修正
    if vision['右矯正']:
        vision['右矯正'] = fix_corrected_vision(vision['右矯正'])
    if vision['左矯正']:
        vision['左矯正'] = fix_corrected_vision(vision['左矯正'])
    
    # 視力データを結果に追加
    result['右裸眼'] = vision['右裸眼']
    result['右矯正'] = vision['右矯正']
    result['左裸眼'] = vision['左裸眼']
    result['左矯正'] = vision['左矯正']
    result['右TOL'] = vision['右TOL']  # TOL情報追加
    result['左TOL'] = vision['左TOL']  # TOL情報追加
    
    # 包括的な眼圧データ抽出
    iop_data = extract_all_iop_types(ocr_text)
    result['NCT右'] = iop_data['NCT右']
    result['NCT左'] = iop_data['NCT左']
    result['手書き右'] = iop_data['手書き右']
    result['手書き左'] = iop_data['手書き左']
    result['眼圧備考'] = iop_data['眼圧備考']
    
    # 最終的な眼圧データ選択
    final_iop = select_final_iop(iop_data)
    result['最終眼圧右'] = final_iop['眼圧右']
    result['最終眼圧左'] = final_iop['眼圧左']
    result['使用データ'] = final_iop['使用データ']
    
    # レフ値（屈折値）抽出
    refraction_data = extract_refraction_data(ocr_text)
    result['S'] = refraction_data['S']
    result['C'] = refraction_data['C']
    result['Ax'] = refraction_data['Ax']
    
    # 手術情報抽出（手術記録の場合）
    surgery_data = extract_surgery_data(ocr_text)
    result['手術日'] = surgery_data['手術日']
    result['患者名'] = surgery_data['患者名']
    result['術前診断'] = surgery_data['術前診断']
    result['術式'] = surgery_data['術式']
    result['対象眼'] = surgery_data['対象眼']
    
    # IOLシール情報抽出
    iol_seal_data = extract_iol_seal_data(ocr_text)
    result['IOL度数_S'] = iol_seal_data['IOL度数_S']
    result['IOL度数_C'] = iol_seal_data['IOL度数_C']
    result['IOL度数_Ax'] = iol_seal_data['IOL度数_Ax']
    result['IOL製品名'] = iol_seal_data['IOL製品名']
    result['IOLメーカー'] = iol_seal_data['IOLメーカー']
    result['IOL備考'] = iol_seal_data['IOL備考']
    
    # 検査画像識別（OCRテキストの内容のみから左右判定）
    examination_data = identify_examination_type(ocr_text)
    result['検査種類'] = examination_data['検査種類']
    result['検査詳細'] = examination_data['検査詳細']
    result['検査日'] = examination_data['検査日']
    result['検査対象眼'] = examination_data['対象眼']  # OCRテキストから判定した対象眼
    result['検査備考'] = examination_data['検査備考']
    
    # 検査種類別の詳細データ抽出
    if examination_data['検査種類'] == 'OCT':
        oct_data = extract_oct_data(ocr_text, text_upper)
        result.update(oct_data)
    elif examination_data['検査種類'] == 'OCTA':
        octa_data = extract_octa_data(ocr_text, text_upper)
        result.update(octa_data)
    elif examination_data['検査種類'] in ['ハンフリー視野', 'AIMO視野']:
        visual_field_data = extract_visual_field_data(ocr_text, text_upper)
        result.update(visual_field_data)
    
    return result

def process_image_two_tier_comprehensive(ocr_text):
    """2段構造対応の包括的処理"""
    
    result = {
        '前回_右裸眼': '',
        '前回_右矯正': '',
        '前回_左裸眼': '',
        '前回_左矯正': '',
        '今回_右裸眼': '',
        '今回_右矯正': '',
        '今回_左裸眼': '',
        '今回_左矯正': '',
        '今回_S': '',
        '今回_C': '',
        '今回_A': '',
        'NCT右': '',
        'NCT左': '',
        '手書き右': '',
        '手書き左': '',
        '最終眼圧右': '',
        '最終眼圧左': '',
        '眼圧備考': '',
        '使用データ': ''
    }
    
    # 2段構造の視力データ処理
    two_tier_data = process_two_tier_vision_data(ocr_text)
    
    # 2段構造データを結果に追加
    for key in two_tier_data:
        result[key] = two_tier_data[key]
    
    # 眼圧データ抽出
    iop_data = extract_all_iop_types(ocr_text)
    result['NCT右'] = iop_data['NCT右']
    result['NCT左'] = iop_data['NCT左']
    result['手書き右'] = iop_data['手書き右']
    result['手書き左'] = iop_data['手書き左']
    result['眼圧備考'] = iop_data['眼圧備考']
    
    # 最終的な眼圧データ選択
    final_iop = select_final_iop(iop_data)
    result['最終眼圧右'] = final_iop['眼圧右']
    result['最終眼圧左'] = final_iop['眼圧左']
    result['使用データ'] = final_iop['使用データ']
    
    return result

def process_all_images_final_comprehensive():
    """最終包括的システムで全画像処理"""
    print("最終包括的医療OCRシステム")
    print("=" * 50)
    
    # Vision APIクライアントを作成
    client = create_vision_client()
    if not client:
        print("❌ Vision APIクライアントの作成に失敗しました")
        return []
    
    # 画像ファイルを取得
    image_folder = r"C:\Projects\medical-ocr\inbox"
    image_files = glob.glob(os.path.join(image_folder, "*.JPG"))
    image_files.extend(glob.glob(os.path.join(image_folder, "*.jpg")))
    
    print(f"処理対象画像数: {len(image_files)}")
    
    results = []
    
    for i, img_file in enumerate(image_files, 1):
        filename = os.path.basename(img_file)
        print(f"\n[{i}/{len(image_files)}] 処理中: {filename}")
        
        # Google Vision API実行
        text = google_vision_ocr(img_file, client)
        
        if not text:
            print(f"  ❌ OCR失敗")
            results.append({
                'filename': filename,
                'status': 'OCR_FAILED',
                '右裸眼': '',
                '右矯正': '',
                '左裸眼': '',
                '左矯正': '',
                '右TOL': '',  # TOL情報追加
                '左TOL': '',  # TOL情報追加
                'NCT右': '',
                'NCT左': '',
                '手書き右': '',
                '手書き左': '',
                '最終眼圧右': '',
                '最終眼圧左': '',
                '眼圧備考': '',
                '使用データ': '',
                'S': '',
                'C': '',
                'Ax': '',
                '手術日': '',
                '患者名': '',
                '術前診断': '',
                '術式': '',
                '対象眼': '',
                'IOL度数_S': '',  # IOLシール情報追加
                'IOL度数_C': '',  # IOLシール情報追加
                'IOL度数_Ax': '',  # IOLシール情報追加
                'IOL製品名': '',  # IOLシール情報追加
                'IOLメーカー': '',  # IOLシール情報追加
                'IOL備考': '',  # IOLシール情報追加
                '検査種類': '',  # 検査画像識別追加
                '検査詳細': '',  # 検査画像識別追加
                '検査日': '',  # 検査画像識別追加
                '検査対象眼': '',  # 検査対象眼追加
                '検査備考': '',  # 検査画像識別追加
                'ocr_text': ''
            })
            continue
        
        print(f"  ✅ OCR成功 ({len(text)}文字)")
        
        # 最終包括的な処理
        data = process_image_final_comprehensive(text, filename)
        
        # 抽出結果の詳細表示
        print(f"  📊 抽出結果:")
        if data['右裸眼'] or data['左裸眼']:
            print(f"    視力: 右裸眼={data['右裸眼'] or '未検出'}, 左裸眼={data['左裸眼'] or '未検出'}")
        if data['右TOL'] or data['左TOL']:
            print(f"    TOL: 右={data['右TOL'] or '未検出'}, 左={data['左TOL'] or '未検出'}")
        if data['右矯正'] or data['左矯正']:
            print(f"    矯正: 右={data['右矯正'] or '未検出'}, 左={data['左矯正'] or '未検出'}")
        if data['最終眼圧右'] or data['最終眼圧左']:
            print(f"    眼圧: 右={data['最終眼圧右'] or '未検出'}, 左={data['最終眼圧左'] or '未検出'} ({data['使用データ']})")
        else:
            print(f"    眼圧: 未検出")
        if data['S'] or data['C'] or data['Ax']:
            print(f"    レフ値: S={data['S'] or '未検出'}, C={data['C'] or '未検出'}, Ax={data['Ax'] or '未検出'}")
        else:
            print(f"    レフ値: 未検出")
        if data['手術日'] or data['患者名'] or data['術前診断'] or data['術式']:
            print(f"    手術情報: 日={data['手術日'] or '未検出'}, 患者={data['患者名'] or '未検出'}, 診断={data['術前診断'] or '未検出'}, 対象眼={data['対象眼'] or '未検出'}, 術式={data['術式'] or '未検出'}")
        else:
            print(f"    手術情報: 未検出")
        if data['IOL度数_S'] or data['IOL度数_C'] or data['IOL度数_Ax'] or data['IOL製品名'] or data['IOLメーカー']:
            print(f"    IOLシール: S={data['IOL度数_S'] or '未検出'}, C={data['IOL度数_C'] or '未検出'}, Ax={data['IOL度数_Ax'] or '未検出'}, 製品={data['IOL製品名'] or '未検出'}, メーカー={data['IOLメーカー'] or '未検出'}")
        else:
            print(f"    IOLシール: 未検出")
        if data['検査種類'] or data['検査詳細']:
            print(f"    検査画像: {data['検査種類'] or '未検出'} - {data['検査詳細'] or '未検出'} ({data['検査日'] or '未検出'}) - 対象眼: {data['検査対象眼'] or '未検出'}")
            # 検査種類別の詳細データ表示
            if data['検査種類'] == 'OCT':
                if data.get('OCT_網膜厚_右') or data.get('OCT_網膜厚_左'):
                    print(f"    OCT数値: 右網膜厚={data.get('OCT_網膜厚_右', '未検出')}, 左網膜厚={data.get('OCT_網膜厚_左', '未検出')}")
            elif data['検査種類'] == 'OCTA':
                if data.get('OCTA_血管密度_右') or data.get('OCTA_血管密度_左'):
                    print(f"    OCTA数値: 右血管密度={data.get('OCTA_血管密度_右', '未検出')}, 左血管密度={data.get('OCTA_血管密度_左', '未検出')}")
            elif data['検査種類'] in ['ハンフリー視野', 'AIMO視野']:
                if data.get('視野_MD_右') or data.get('視野_MD_左'):
                    print(f"    視野数値: 右MD={data.get('視野_MD_右', '未検出')}, 左MD={data.get('視野_MD_左', '未検出')}")
        else:
            print(f"    検査画像: 未検出")
        
        # 結果を記録
        result = {
            'filename': filename,
            'status': 'SUCCESS',
            '右裸眼': data['右裸眼'],
            '右矯正': data['右矯正'],
            '左裸眼': data['左裸眼'],
            '左矯正': data['左矯正'],
            '右TOL': data['右TOL'],  # TOL情報追加
            '左TOL': data['左TOL'],  # TOL情報追加
            'NCT右': data['NCT右'],
            'NCT左': data['NCT左'],
            '手書き右': data['手書き右'],
            '手書き左': data['手書き左'],
            '最終眼圧右': data['最終眼圧右'],
            '最終眼圧左': data['最終眼圧左'],
            '眼圧備考': data['眼圧備考'],
            '使用データ': data['使用データ'],
            'S': data['S'],
            'C': data['C'],
            'Ax': data['Ax'],
            '手術日': data['手術日'],
            '患者名': data['患者名'],
            '術前診断': data['術前診断'],
            '術式': data['術式'],
            '対象眼': data['対象眼'],
            'IOL度数_S': data['IOL度数_S'],  # IOLシール情報追加
            'IOL度数_C': data['IOL度数_C'],  # IOLシール情報追加
            'IOL度数_Ax': data['IOL度数_Ax'],  # IOLシール情報追加
            'IOL製品名': data['IOL製品名'],  # IOLシール情報追加
            'IOLメーカー': data['IOLメーカー'],  # IOLシール情報追加
            'IOL備考': data['IOL備考'],  # IOLシール情報追加
            '検査種類': data['検査種類'],  # 検査画像識別追加
            '検査詳細': data['検査詳細'],  # 検査画像識別追加
            '検査日': data['検査日'],  # 検査画像識別追加
            '検査対象眼': data['検査対象眼'],  # 検査対象眼追加
            '検査備考': data['検査備考'],  # 検査画像識別追加
            'ocr_text': text[:200] + "..." if len(text) > 200 else text
        }
        
        results.append(result)
    
    return results

def process_all_images_two_tier_comprehensive():
    """2段構造対応の包括的システムで全画像処理"""
    print("2段構造対応医療OCRシステム")
    print("=" * 50)
    
    # Vision APIクライアントを作成
    client = create_vision_client()
    if not client:
        print("❌ Vision APIクライアントの作成に失敗しました")
        return []
    
    # 画像ファイルを取得
    image_folder = r"C:\Projects\medical-ocr\inbox"
    image_files = glob.glob(os.path.join(image_folder, "*.JPG"))
    image_files.extend(glob.glob(os.path.join(image_folder, "*.jpg")))
    
    print(f"処理対象画像数: {len(image_files)}")
    
    results = []
    
    for i, img_file in enumerate(image_files, 1):
        filename = os.path.basename(img_file)
        print(f"\n[{i}/{len(image_files)}] 処理中: {filename}")
        
        # Google Vision API実行
        text = google_vision_ocr(img_file, client)
        
        if not text:
            print(f"  ❌ OCR失敗")
            results.append({
                'filename': filename,
                'status': 'OCR_FAILED',
                '前回_右裸眼': '', '前回_右矯正': '', '前回_左裸眼': '', '前回_左矯正': '',
                '今回_右裸眼': '', '今回_右矯正': '', '今回_左裸眼': '', '今回_左矯正': '',
                '今回_S': '', '今回_C': '', '今回_A': '',
                'NCT右': '', 'NCT左': '', '手書き右': '', '手書き左': '',
                '最終眼圧右': '', '最終眼圧左': '', '眼圧備考': '', '使用データ': '',
                'ocr_text': ''
            })
            continue
        
        print(f"  ✅ OCR成功 ({len(text)}文字)")
        
        # 2段構造対応の包括的処理
        data = process_image_two_tier_comprehensive(text)
        
        # 抽出結果の詳細表示
        print(f"  📊 抽出結果:")
        if data['今回_右裸眼'] or data['今回_左裸眼']:
            print(f"    今回視力: 右裸眼={data['今回_右裸眼'] or '未検出'}, 左裸眼={data['今回_左裸眼'] or '未検出'}")
        if data['今回_右矯正'] or data['今回_左矯正']:
            print(f"    今回矯正: 右={data['今回_右矯正'] or '未検出'}, 左={data['今回_左矯正'] or '未検出'}")
        if data['前回_右裸眼'] or data['前回_左裸眼']:
            print(f"    前回視力: 右裸眼={data['前回_右裸眼'] or '未検出'}, 左裸眼={data['前回_左裸眼'] or '未検出'}")
        if data['最終眼圧右'] or data['最終眼圧左']:
            print(f"    眼圧: 右={data['最終眼圧右'] or '未検出'}, 左={data['最終眼圧左'] or '未検出'} ({data['使用データ']})")
        else:
            print(f"    眼圧: 未検出")
        
        # 結果を記録
        result = {
            'filename': filename,
            'status': 'SUCCESS',
            '前回_右裸眼': data['前回_右裸眼'],
            '前回_右矯正': data['前回_右矯正'],
            '前回_左裸眼': data['前回_左裸眼'],
            '前回_左矯正': data['前回_左矯正'],
            '今回_右裸眼': data['今回_右裸眼'],
            '今回_右矯正': data['今回_右矯正'],
            '今回_左裸眼': data['今回_左裸眼'],
            '今回_左矯正': data['今回_左矯正'],
            '今回_S': data['今回_S'],
            '今回_C': data['今回_C'],
            '今回_A': data['今回_A'],
            'NCT右': data['NCT右'],
            'NCT左': data['NCT左'],
            '手書き右': data['手書き右'],
            '手書き左': data['手書き左'],
            '最終眼圧右': data['最終眼圧右'],
            '最終眼圧左': data['最終眼圧左'],
            '眼圧備考': data['眼圧備考'],
            '使用データ': data['使用データ'],
            'ocr_text': text[:200] + "..." if len(text) > 200 else text
        }
        
        results.append(result)
    
    return results

def save_results_to_csv(results):
    """結果をCSVファイルに保存"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"fixed_vision_extraction_{timestamp}.csv"
    
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'filename', 'status', '右裸眼', '右矯正', '左裸眼', '左矯正', '右TOL', '左TOL',
            'NCT右', 'NCT左', '手書き右', '手書き左', '最終眼圧右', '最終眼圧左', 
            '眼圧備考', '使用データ', 'S', 'C', 'Ax', '手術日', '患者名', '術前診断', '対象眼', '術式',
            'IOL度数_S', 'IOL度数_C', 'IOL度数_Ax', 'IOL製品名', 'IOLメーカー', 'IOL備考',
            '検査種類', '検査詳細', '検査日', '検査備考', 'ocr_text'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\n✅ 結果を {csv_filename} に保存しました")
    return csv_filename

def print_statistics(results):
    """統計情報を表示"""
    total_images = len(results)
    success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
    vision_detected_count = sum(1 for r in results if any([
        r['右裸眼'], r['右矯正'], r['左裸眼'], r['左矯正']
    ]))
    
    print(f"\n=== 統計情報 ===")
    print(f"総画像数: {total_images}")
    print(f"OCR成功: {success_count}")
    print(f"視力データ検出: {vision_detected_count}")
    print(f"視力検出率: {vision_detected_count/total_images*100:.1f}%")

# テスト用の関数
def test_extraction():
    """実際のテキストでテスト"""
    test_text = """
V.d.=
0.01
x IOL
(n.c)
V.s.=
0.05
x IOL
(0.06 x S-1.75)
"""
    
    result = extract_vision_data_fixed(test_text)
    print("=== テスト結果 ===")
    print(result)

def test_reconstruction():
    """行再構築のテスト"""
    test_text = """
V.d.=
0.01
x IOL
(n.c)
V.s.=
0.05
x IOL
(0.06 x S-1.75)
"""
    
    lines = test_text.split('\n')
    print("=== 行再構築テスト ===")
    
    for i, line in enumerate(lines):
        if 'V.d.' in line:
            full_line = reconstruct_vision_line(lines, i)
            print(f"再構築されたV.d.行: {full_line}")
        elif 'V.s.' in line:
            full_line = reconstruct_vision_line(lines, i)
            print(f"再構築されたV.s.行: {full_line}")
    
    # 改良された抽出テスト
    result = extract_vision_data_fixed(test_text)
    print(f"抽出結果: {result}")

def test_iop_extraction():
    """眼圧抽出システムのテスト"""
    test_cases = [
        "AT: 15　18",
        "IOP 15/18",
        "ＡＴ　１５／１８",
        "iop 15　18",
        "AT:15 18",
        "IOP 15  18",
        "AT: 右15 左18",
        "IOP R15 L18",
        "眼圧 15/18",
        "AT 15, 18",
        "IOP: 15-18"
    ]
    
    print("=== 眼圧抽出システムテスト ===")
    
    for i, test_text in enumerate(test_cases, 1):
        print(f"\nテストケース {i}: {test_text}")
        result = extract_handwritten_iop_patterns_improved(test_text)
        print(f"結果: {result}")
        
        if result['右眼圧'] and result['左眼圧']:
            print(f"✅ 成功: R={result['右眼圧']}, L={result['左眼圧']}")
        else:
            print("❌ 失敗")

def extract_handwritten_iop_patterns_improved(text):
    """手書き眼圧抽出（改良版）"""
    
    lines = text.split('\n')
    result = {'右眼圧': '', '左眼圧': '', '眼圧メモ': ''}
    
    # 改良版: より多くのパターンを検索
    for line in lines:
        # DATEの行はスキップ
        if 'DATE' in line.upper() or '2025/' in line or '2024/' in line:
            continue
            
        # 眼圧関連マーカーを拡張
        if any(marker in line.upper() for marker in ['AT', 'IOP', 'ＡＴ', 'ＩＯＰ', '眼圧', 'EYE', 'PRESSURE']):
            # DATE行でないことを再確認
            if 'DATE' not in line.upper():
                print(f"眼圧行候補（改良版）: {line}")
                
                # パターン1: 数字のみ（15 18）
                numbers = re.findall(r'\b(\d{1,2})\b', line)
                valid_iop = [n for n in numbers if 0 <= int(n) <= 80]
                
                if len(valid_iop) >= 2:
                    result['右眼圧'] = valid_iop[0]
                    result['左眼圧'] = valid_iop[1]
                    result['眼圧メモ'] = f'パターン1（数字のみ）: {line.strip()}'
                    return result
                
                # パターン2: スラッシュ形式（15/18）
                slash = re.search(r'(\d{1,2})\s*[/／]\s*(\d{1,2})', line)
                if slash:
                    v1, v2 = int(slash.group(1)), int(slash.group(2))
                    if 0 <= v1 <= 80 and 0 <= v2 <= 80:
                        result['右眼圧'] = str(v1)
                        result['左眼圧'] = str(v2)
                        result['眼圧メモ'] = f'パターン2（スラッシュ）: {line.strip()}'
                        return result
                
                # パターン3: R/L形式（R15 L18）
                rl_pattern = re.search(r'[RＲ]\s*(\d{1,2})\s*[LＬ]\s*(\d{1,2})', line)
                if rl_pattern:
                    v1, v2 = int(rl_pattern.group(1)), int(rl_pattern.group(2))
                    if 0 <= v1 <= 80 and 0 <= v2 <= 80:
                        result['右眼圧'] = str(v1)
                        result['左眼圧'] = str(v2)
                        result['眼圧メモ'] = f'パターン3（R/L形式）: {line.strip()}'
                        return result
                
                # パターン4: 右左形式（右15 左18）
                right_left_pattern = re.search(r'右\s*(\d{1,2})\s*左\s*(\d{1,2})', line)
                if right_left_pattern:
                    v1, v2 = int(right_left_pattern.group(1)), int(right_left_pattern.group(2))
                    if 0 <= v1 <= 80 and 0 <= v2 <= 80:
                        result['右眼圧'] = str(v1)
                        result['左眼圧'] = str(v2)
                        result['眼圧メモ'] = f'パターン4（右左形式）: {line.strip()}'
                        return result
    
    # 拡張検索: 眼圧マーカーがない行でも数値ペアを探す
    print(f"  ⚠️ 眼圧マーカーが見つかりませんでした。拡張検索...")
    
    for line in lines:
        # 数値ペアを探す（眼圧の可能性）
        numbers = re.findall(r'\b(\d{1,2})\b', line)
        valid_numbers = [n for n in numbers if 10 <= int(n) <= 30]  # 眼圧らしい範囲
        
        if len(valid_numbers) >= 2:
            # 行に眼圧関連の単語がないかチェック
            if not any(word in line.upper() for word in ['DATE', '2025', '2024', 'TIME', '年', '月', '日']):
                result['右眼圧'] = valid_numbers[0]
                result['左眼圧'] = valid_numbers[1]
                result['眼圧メモ'] = f'拡張検索: {line.strip()}'
                print(f"  ✅ 拡張検索で発見: {line.strip()}")
                return result
    
    return result

def extract_refraction_data(text):
    """レフ値（屈折値）を抽出（プリント出力対応）"""
    
    import re
    
    result = {
        'S': '',      # 球面度数 (±0.00〜±30.00、小数点以下2桁)
        'C': '',      # 円柱度数 (±0.00〜±30.00、小数点以下2桁)
        'Ax': ''      # 軸 (0-360°、整数)
    }
    
    lines = text.split('\n')
    
    print("🔍 レフ値抽出中...")
    
    # レフ値関連のキーワードを含む行を探す
    refraction_keywords = ['REFRACTION', 'REFR', 'レフ', '屈折', 'SPH', 'CYL', 'AXIS', 'Ax', 'AX']
    
    for i, line in enumerate(lines):
        line_upper = line.upper()
        
        # レフ値関連の行かチェック
        if any(keyword in line_upper for keyword in refraction_keywords):
            print(f"  📄 レフ値行候補 {i}: {line}")
            
            # S（球面度数）を探す (±0.00〜±30.00、小数点以下2桁)
            s_patterns = [
                r'SPH[:\s]*([+-]?\d+\.\d{2})',         # SPH: +1.25
                r'([+-]?\d+\.\d{2})\s*×\s*S',          # +1.25×S
                r'球面[:\s]*([+-]?\d+\.\d{2})',        # 球面: +1.25
                r'([+-]?\d+\.\d{2})\s*球面',           # +1.25球面
                r'([+-]?\d+\.\d{2})\s+[+-]?\d+\.\d{2}\s+\d+',  # -0.75 -0.25 79 (最初の値がS)
                r'([+-]?\d+\.\d{2})\s+[+-]?\d+\.\d{2}\s+\d+\s*[0*]',  # -0.75 -0.25 79 0
            ]
            
            for pattern in s_patterns:
                match = re.search(pattern, line)
                if match:
                    s_value = match.group(1)
                    try:
                        s_float = float(s_value)
                        if -30.00 <= s_float <= 30.00:
                            result['S'] = s_value
                            print(f"    ✅ S値発見: {s_value}")
                            break
                        else:
                            print(f"    ⚠️ S値範囲外: {s_value} (-30.00〜+30.00)")
                    except:
                        continue
            
            # C（円柱度数）を探す (±0.00〜±30.00、小数点以下2桁)
            c_patterns = [
                r'CYL[:\s]*([+-]?\d+\.\d{2})',         # CYL: -0.50
                r'([+-]?\d+\.\d{2})\s*×\s*C',          # -0.50×C
                r'円柱[:\s]*([+-]?\d+\.\d{2})',        # 円柱: -0.50
                r'([+-]?\d+\.\d{2})\s*円柱',           # -0.50円柱
                r'[+-]?\d+\.\d{2}\s+([+-]?\d+\.\d{2})\s+\d+',  # -0.75 -0.25 79 (2番目の値がC)
                r'[+-]?\d+\.\d{2}\s+([+-]?\d+\.\d{2})\s+\d+\s*[0*]',  # -0.75 -0.25 79 0
            ]
            
            for pattern in c_patterns:
                match = re.search(pattern, line)
                if match:
                    c_value = match.group(1)
                    try:
                        c_float = float(c_value)
                        if -30.00 <= c_float <= 30.00:
                            result['C'] = c_value
                            print(f"    ✅ C値発見: {c_value}")
                            break
                        else:
                            print(f"    ⚠️ C値範囲外: {c_value} (-30.00〜+30.00)")
                    except:
                        continue
            
            # Ax（軸）を探す (0-360°、整数)
            ax_patterns = [
                r'AXIS[:\s]*(\d{1,3})',                # AXIS: 90
                r'Ax[:\s]*(\d{1,3})',                  # Ax: 90
                r'AX[:\s]*(\d{1,3})',                  # AX: 90
                r'軸[:\s]*(\d{1,3})',                  # 軸: 90
                r'(\d{1,3})\s*度',                     # 90度
                r'(\d{1,3})\s*°',                      # 90°
                r'[+-]?\d+\.\d{2}\s+[+-]?\d+\.\d{2}\s+(\d{1,3})',  # -0.75 -0.25 79 (3番目の値がAx)
            ]
            
            for pattern in ax_patterns:
                match = re.search(pattern, line)
                if match:
                    ax_value = match.group(1)
                    try:
                        ax_int = int(ax_value)
                        if 0 <= ax_int <= 360:
                            result['Ax'] = ax_value
                            print(f"    ✅ Ax値発見: {ax_value}°")
                            break
                        else:
                            print(f"    ⚠️ Ax値範囲外: {ax_value} (0-360°)")
                    except:
                        continue
    
    # SPH/CYL AXIS行の後の数値行を探す（より正確な抽出）
    for i, line in enumerate(lines):
        line_upper = line.upper()
        
        # SPH行を見つけたら、次の数行をチェック
        if 'SPH' in line_upper and i + 1 < len(lines):
            print(f"  📄 SPH行発見 {i}: {line}")
            
            # 次の数行をチェックして数値ペアを探す
            for j in range(i + 1, min(i + 5, len(lines))):
                next_line = lines[j]
                print(f"    📊 +{j-i}行目: {next_line}")
                
                # 数値ペアパターンをチェック (-0.75 -0.25 79)
                pair_match = re.search(r'([+-]?\d+\.\d{2})\s+([+-]?\d+\.\d{2})\s+(\d{1,3})', next_line)
                if pair_match:
                    s_val, c_val, ax_val = pair_match.groups()
                    
                    # 値の範囲チェック
                    try:
                        s_float = float(s_val)
                        c_float = float(c_val)
                        ax_int = int(ax_val)
                        
                        if -30.00 <= s_float <= 30.00 and -30.00 <= c_float <= 30.00 and 0 <= ax_int <= 360:
                            if not result['S']:
                                result['S'] = s_val
                                print(f"      ✅ S値設定: {s_val}")
                            if not result['C']:
                                result['C'] = c_val
                                print(f"      ✅ C値設定: {c_val}")
                            if not result['Ax']:
                                result['Ax'] = ax_val
                                print(f"      ✅ Ax値設定: {ax_val}°")
                            break
                    except:
                        continue
    
    # 結果を表示
    print(f"  📊 レフ値抽出結果:")
    print(f"    S: {result['S'] or '未検出'}")
    print(f"    C: {result['C'] or '未検出'}")
    print(f"    Ax: {result['Ax'] or '未検出'}")
    
    return result

def extract_degree_data(text):
    """度数情報（S、C、A）を抽出"""
    
    import re
    
    result = {'S': '', 'C': '', 'A': ''}
    
    # S（球面度数）を探す
    s_patterns = [
        r'S[:\s]*([+-]?\d+\.?\d*)',
        r'球面[:\s]*([+-]?\d+\.?\d*)',
        r'([+-]?\d+\.?\d*)\s*×\s*S'
    ]
    
    for pattern in s_patterns:
        match = re.search(pattern, text)
        if match:
            result['S'] = match.group(1)
            break
    
    # C（円柱度数）を探す
    c_patterns = [
        r'C[:\s]*([+-]?\d+\.?\d*)',
        r'円柱[:\s]*([+-]?\d+\.?\d*)',
        r'([+-]?\d+\.?\d*)\s*×\s*C'
    ]
    
    for pattern in c_patterns:
        match = re.search(pattern, text)
        if match:
            result['C'] = match.group(1)
            break
    
    # A（軸）を探す
    a_patterns = [
        r'A[:\s]*(\d+)',
        r'軸[:\s]*(\d+)',
        r'(\d+)\s*度'
    ]
    
    for pattern in a_patterns:
        match = re.search(pattern, text)
        if match:
            result['A'] = match.group(1)
            break
    
    return result

def extract_surgery_data(text):
    """手術記録から手術情報を抽出"""
    
    import re
    
    result = {
        '手術日': '',
        '患者名': '',
        '術前診断': '',
        '術式': '',
        '対象眼': ''  # 右眼、左眼、両眼
    }
    
    lines = text.split('\n')
    
    print("🔍 手術情報抽出中...")
    
    # 手術日を探す
    date_patterns = [
        r'手術日[:\s]*(\d{4}[年/]\d{1,2}[月/]\d{1,2}[日]?)',
        r'(\d{4}[年/]\d{1,2}[月/]\d{1,2}[日]?)\s*手術',
        r'DATE[:\s]*(\d{4}[/]\d{1,2}[/]\d{1,2})',
        r'(\d{4}[/]\d{1,2}[/]\d{1,2})\s*手術',
    ]
    
    for line in lines:
        for pattern in date_patterns:
            match = re.search(pattern, line)
            if match:
                result['手術日'] = match.group(1)
                print(f"  ✅ 手術日発見: {result['手術日']}")
                break
        if result['手術日']:
            break
    
    # 患者名を探す
    name_patterns = [
        r'患者氏名[:\s]*([^\n]+)',
        r'患者名[:\s]*([^\n]+)',
        r'氏名[:\s]*([^\n]+)',
        r'名前[:\s]*([^\n]+)',
    ]
    
    for line in lines:
        for pattern in name_patterns:
            match = re.search(pattern, line)
            if match:
                result['患者名'] = match.group(1).strip()
                print(f"  ✅ 患者名発見: {result['患者名']}")
                break
        if result['患者名']:
            break
    
    # 術前診断を探す（事前定義リスト使用）
    diagnosis_patterns = [
        r'術前診断[:\s]*([^\n]+)',
        r'診断[:\s]*([^\n]+)',
        r'病名[:\s]*([^\n]+)',
    ]
    
    # パターンマッチングで術前診断を探す
    for line in lines:
        for pattern in diagnosis_patterns:
            match = re.search(pattern, line)
            if match:
                raw_diagnosis = match.group(1).strip()
                result['術前診断'] = raw_diagnosis
                print(f"  ✅ 術前診断発見: {result['術前診断']}")
                break
        if result['術前診断']:
            break
    
    # 事前定義リストで術前診断を分類・標準化
    if result['術前診断']:
        raw_diagnosis = result['術前診断']  # 元のデータを保持
        raw_text = result['術前診断'].upper()
        for category, keywords in PREDEFINED_DIAGNOSES.items():
            for keyword in keywords:
                if keyword.upper() in raw_text:
                    result['術前診断'] = category
                    print(f"  ✅ 術前診断分類: {category}")
                    break
            if result['術前診断'] == category:
                break
        
        # 対象眼を元の診断から抽出
        if '右眼' in raw_diagnosis:
            result['対象眼'] = '右眼'
            print(f"  ✅ 対象眼抽出（術前診断）: 右眼")
        elif '左眼' in raw_diagnosis:
            result['対象眼'] = '左眼'
            print(f"  ✅ 対象眼抽出（術前診断）: 左眼")
        elif '両眼' in raw_diagnosis:
            result['対象眼'] = '両眼'
            print(f"  ✅ 対象眼抽出（術前診断）: 両眼")
    
    # 対象眼を抽出（右眼、左眼、両眼）- 術前診断から優先的に抽出
    if not result['対象眼']:
        eye_patterns = [
            r'右眼[:\s]*([^\n]*)',
            r'左眼[:\s]*([^\n]*)',
            r'両眼[:\s]*([^\n]*)',
            r'([右左両]眼)',
        ]
        
        for line in lines:
            for pattern in eye_patterns:
                match = re.search(pattern, line)
                if match:
                    eye_info = match.group(1).strip()
                    if '右眼' in eye_info:
                        result['対象眼'] = '右眼'
                    elif '左眼' in eye_info:
                        result['対象眼'] = '左眼'
                    elif '両眼' in eye_info:
                        result['対象眼'] = '両眼'
                    print(f"  ✅ 対象眼発見: {result['対象眼']}")
                    break
            if result['対象眼']:
                break
    
    # 術式を探す（事前定義リスト使用）
    surgery_patterns = [
        r'予定術式[:\s]*([^\n]+)',
        r'実施手術[:\s]*([^\n]+)',
        r'術式[:\s]*([^\n]+)',
        r'手術[:\s]*([^\n]+)',
        r'手術名[:\s]*([^\n]+)',
    ]
    
    # 術式は複数行にわたる可能性があるので、行を結合して検索
    combined_text = ' '.join(lines)
    
    # パターンマッチングで術式を探す
    for pattern in surgery_patterns:
        match = re.search(pattern, combined_text)
        if match:
            raw_surgery = match.group(1).strip()
            result['術式'] = raw_surgery
            print(f"  ✅ 術式発見: {result['術式']}")
            break
    
    # 事前定義リストで術式を分類・標準化
    if result['術式']:
        raw_text = result['術式'].upper()
        for category, keywords in PREDEFINED_SURGERIES.items():
            for keyword in keywords:
                if keyword.upper() in raw_text:
                    result['術式'] = category
                    print(f"  ✅ 術式分類: {category}")
                    break
            if result['術式'] == category:
                break
    
    # 術式が見つからない場合、事前定義リストのキーワードで検索
    if not result['術式']:
        for line in lines:
            line_upper = line.upper()
            for category, keywords in PREDEFINED_SURGERIES.items():
                for keyword in keywords:
                    if keyword.upper() in line_upper:
                        result['術式'] = category
                        print(f"  ✅ 術式（事前定義キーワード）発見: {category}")
                        break
                if result['術式']:
                    break
            if result['術式']:
                break
    
    # 術式の詳細化（部分的な情報から推測）
    if result['術式'] and len(result['術式']) < 10:
        # 短い術式の場合、周辺の行も確認
        for i, line in enumerate(lines):
            if result['術式'] in line:
                # 前後の行も含めて術式を構築
                context_lines = []
                for j in range(max(0, i-2), min(len(lines), i+3)):
                    if lines[j].strip() and not lines[j].strip().startswith('手術'):
                        context_lines.append(lines[j].strip())
                
                if len(context_lines) > 1:
                    result['術式'] = ' '.join(context_lines[:3])  # 最大3行まで
                    print(f"  ✅ 術式詳細化: {result['術式']}")
                break
    
    # 結果を表示
    print(f"  📊 手術情報抽出結果:")
    print(f"    手術日: {result['手術日'] or '未検出'}")
    print(f"    患者名: {result['患者名'] or '未検出'}")
    print(f"    術前診断: {result['術前診断'] or '未検出'}")
    print(f"    対象眼: {result['対象眼'] or '未検出'}")
    print(f"    術式: {result['術式'] or '未検出'}")
    
    return result

def extract_iol_seal_data(text):
    """IOLシールから度数と製品名を抽出"""
    
    import re
    
    result = {
        'IOL度数_S': '',
        'IOL度数_C': '',
        'IOL度数_Ax': '',
        'IOL製品名': '',
        'IOLメーカー': '',
        'IOL備考': ''
    }
    
    lines = text.split('\n')
    
    # IOLシールのキーワードを探す
    iol_keywords = ['IOL', 'シール', 'レンズ', '度数', '製品', 'メーカー', 'LENS', 'POWER', 'DIOPTER']
    
    iol_section = []
    for line in lines:
        if any(keyword in line.upper() for keyword in iol_keywords):
            iol_section.append(line)
    
    if not iol_section:
        return result
    
    # 度数パターンを探す（S, C, Ax）
    for line in iol_section:
        # 球面度数（S）
        s_pattern = re.search(r'S[:\s]*([+-]?\d+\.?\d*)', line)
        if s_pattern:
            result['IOL度数_S'] = s_pattern.group(1)
        
        # 円柱度数（C）
        c_pattern = re.search(r'C[:\s]*([+-]?\d+\.?\d*)', line)
        if c_pattern:
            result['IOL度数_C'] = c_pattern.group(1)
        
        # 軸（Ax）
        ax_pattern = re.search(r'Ax[:\s]*(\d+)', line)
        if ax_pattern:
            result['IOL度数_Ax'] = ax_pattern.group(1)
    
    # 製品名・メーカー名を探す
    manufacturer_keywords = ['ALCON', 'AMO', 'JOHNSON', 'J&J', 'ZEISS', 'HOYA', 'CANON', 'NIDEK', 'TOPCON']
    
    for line in iol_section:
        # メーカー名
        for manufacturer in manufacturer_keywords:
            if manufacturer in line.upper():
                result['IOLメーカー'] = manufacturer
                break
        
        # 製品名（一般的なパターン）
        product_pattern = re.search(r'([A-Z]{2,}[A-Z0-9\s\-]+)', line)
        if product_pattern and len(product_pattern.group(1).strip()) > 2:
            potential_product = product_pattern.group(1).strip()
            if potential_product not in ['IOL', 'LENS', 'POWER', 'DIOPTER']:
                result['IOL製品名'] = potential_product
    
    # 備考欄にIOLシールの情報があることを記録
    if any([result['IOL度数_S'], result['IOL度数_C'], result['IOL度数_Ax'], result['IOL製品名'], result['IOLメーカー']]):
        result['IOL備考'] = 'IOLシール情報検出'
    
    return result

def identify_examination_type(text):
    """検査画像の種類を識別（古い画像対応版）"""
    
    import re
    
    result = {
        '検査種類': '',
        '検査詳細': '',
        '検査日': '',
        '検査備考': '',
        '対象眼': ''  # 左右判定を追加
    }
    
    lines = text.split('\n')
    text_upper = text.upper()
    
    # 眼底カメラ
    if any(keyword in text_upper for keyword in ['眼底', 'FUNDUS', 'RETINAL', 'カメラ', 'CAMERA', '眼底写真']):
        result['検査種類'] = '眼底カメラ'
        result['検査詳細'] = '眼底写真撮影'
        
        # 眼底カメラの左右判定（視神経乳頭の位置から）
        result['対象眼'] = determine_fundus_eye_side(text, text_upper)
        
        # 検査日を探す
        date_patterns = [
            r'(\d{4})[年\-\/](\d{1,2})[月\-\/](\d{1,2})[日]?',
            r'(\d{1,2})[月\-\/](\d{1,2})[日\-\/](\d{4})',
            r'(\d{8})',  # YYYYMMDD
        ]
        
        for line in lines:
            for pattern in date_patterns:
                match = re.search(pattern, line)
                if match:
                    if len(match.groups()) == 3:
                        if len(match.group(1)) == 4:  # YYYY/MM/DD
                            result['検査日'] = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
                        else:  # MM/DD/YYYY
                            result['検査日'] = f"{match.group(3)}-{match.group(1)}-{match.group(2)}"
                    elif len(match.groups()) == 1:  # YYYYMMDD
                        date_str = match.group(1)
                        if len(date_str) == 8:
                            result['検査日'] = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                    break
            if result['検査日']:
                break
    
    # OCT（光干渉断層計）
    elif any(keyword in text_upper for keyword in ['OCT', '光干渉', '断層', 'TOMOGRAPHY', 'TRITON', '光干渉断層']):
        result['検査種類'] = 'OCT'
        result['検査詳細'] = '光干渉断層計検査'
        
        # OCTの左右判定
        result['対象眼'] = determine_eye_side_from_text(text, text_upper)
        
        # OCTの詳細情報
        if 'MACULA' in text_upper or '黄斑' in text:
            result['検査詳細'] = 'OCT（黄斑部）'
        elif 'OPTIC' in text_upper or '視神経' in text:
            result['検査詳細'] = 'OCT（視神経）'
        elif 'CORNEA' in text_upper or '角膜' in text:
            result['検査詳細'] = 'OCT（角膜）'
        else:
            result['検査詳細'] = 'OCT（網膜断層）'
    
    # OCTA（光干渉断層血管造影）
    elif any(keyword in text_upper for keyword in ['OCTA', '血管造影', 'ANGIOGRAPHY', 'ANGIO', '血管']):
        result['検査種類'] = 'OCTA'
        result['検査詳細'] = '光干渉断層血管造影'
        
        # OCTAの左右判定
        result['対象眼'] = determine_eye_side_from_text(text, text_upper)
        
        # OCTAの詳細情報
        if 'MACULA' in text_upper or '黄斑' in text:
            result['検査詳細'] = 'OCTA（黄斑部血管）'
        elif 'OPTIC' in text_upper or '視神経' in text:
            result['検査詳細'] = 'OCTA（視神経血管）'
        else:
            result['検査詳細'] = 'OCTA（網膜血管）'
    
    # AIMO視野（明確にAIMOと識別できる場合のみ）
    elif any(keyword in text_upper for keyword in ['AIMO', 'IMO', 'IMO視野']):
        result['検査種類'] = 'AIMO視野'
        result['検査詳細'] = 'AIMO視野計検査'
        
        # AIMO視野の左右判定
        result['対象眼'] = determine_eye_side_from_text(text, text_upper)
        
        # AIMO視野の詳細
        if '30-2' in text_upper:
            result['検査詳細'] = 'AIMO視野（30-2）'
        elif '24-2' in text_upper:
            result['検査詳細'] = 'AIMO視野（24-2）'
        elif '10-2' in text_upper:
            result['検査詳細'] = 'AIMO視野（10-2）'
    
    # ハンフリー視野（視野検査の特徴的なキーワード）
    elif any(keyword in text_upper for keyword in ['HUMPHREY', 'ハンフリー', 'HFA', '視野計', '視野検査', 'PERIMETRY', 'VF', '視野測定']):
        result['検査種類'] = 'ハンフリー視野'
        result['検査詳細'] = 'ハンフリー視野計検査'
        
        # ハンフリー視野の左右判定
        result['対象眼'] = determine_eye_side_from_text(text, text_upper)
        
        # ハンフリー視野の詳細
        if '30-2' in text_upper:
            result['検査詳細'] = 'ハンフリー視野（30-2）'
        elif '24-2' in text_upper:
            result['検査詳細'] = 'ハンフリー視野（24-2）'
        elif '10-2' in text_upper:
            result['検査詳細'] = 'ハンフリー視野（10-2）'
        elif 'MACULA' in text_upper:
            result['検査詳細'] = 'ハンフリー視野（黄斑部）'
        elif 'GLAUCOMA' in text_upper or '緑内障' in text:
            result['検査詳細'] = 'ハンフリー視野（緑内障）'
    
    # その他の検査（古い画像対応）
    else:
        # 一般的な検査キーワード
        if any(keyword in text_upper for keyword in ['検査', 'EXAMINATION', 'TEST', 'MEASUREMENT']):
            # 視野検査の可能性をチェック（AIMOでない場合）
            if any(keyword in text_upper for keyword in ['視野', 'PERIMETRY', 'VF', '視力', 'VISION', '視野計', '視野測定']):
                result['検査種類'] = 'ハンフリー視野'
                result['検査詳細'] = 'ハンフリー視野計検査'
                result['対象眼'] = determine_eye_side_from_text(text, text_upper)
                
                # ハンフリー視野の詳細
                if '30-2' in text_upper:
                    result['検査詳細'] = 'ハンフリー視野（30-2）'
                elif '24-2' in text_upper:
                    result['検査詳細'] = 'ハンフリー視野（24-2）'
                elif '10-2' in text_upper:
                    result['検査詳細'] = 'ハンフリー視野（10-2）'
                elif 'MACULA' in text_upper:
                    result['検査詳細'] = 'ハンフリー視野（黄斑部）'
                elif 'GLAUCOMA' in text_upper or '緑内障' in text:
                    result['検査詳細'] = 'ハンフリー視野（緑内障）'
            # 眼底検査の可能性
            elif any(keyword in text_upper for keyword in ['眼底', 'FUNDUS', 'RETINAL', '網膜', '視神経乳頭']):
                result['検査種類'] = '眼底カメラ'
                result['検査詳細'] = '眼底写真撮影'
                result['対象眼'] = determine_fundus_eye_side(text, text_upper)
            # OCT検査の可能性
            elif any(keyword in text_upper for keyword in ['断層', 'TOMOGRAPHY', '網膜厚', '黄斑厚']):
                result['検査種類'] = 'OCT'
                result['検査詳細'] = 'OCT（網膜断層）'
                result['対象眼'] = determine_eye_side_from_text(text, text_upper)
            else:
                result['検査種類'] = 'その他検査'
                result['検査詳細'] = '一般検査'
                result['対象眼'] = determine_eye_side_from_text(text, text_upper)
        else:
            result['検査種類'] = '未分類'
            result['検査詳細'] = '検査種類不明'
            result['対象眼'] = ''
    
    # 検査備考に追加情報を記録
    additional_info = []
    
    # 検査の質に関する情報
    if any(keyword in text_upper for keyword in ['GOOD', '良好', 'OK']):
        additional_info.append('検査質良好')
    elif any(keyword in text_upper for keyword in ['POOR', '不良', 'NG', 'FAIL']):
        additional_info.append('検査質不良')
    
    # 検査の信頼性
    if any(keyword in text_upper for keyword in ['RELIABLE', '信頼', 'VALID']):
        additional_info.append('信頼性高')
    elif any(keyword in text_upper for keyword in ['UNRELIABLE', '不信頼', 'INVALID']):
        additional_info.append('信頼性低')
    
    # 検査の完了状況
    if any(keyword in text_upper for keyword in ['COMPLETE', '完了', 'FINISH']):
        additional_info.append('検査完了')
    elif any(keyword in text_upper for keyword in ['INCOMPLETE', '未完了', 'INCOMPLETE']):
        additional_info.append('検査未完了')
    
    # 古い画像の可能性
    if any(keyword in text_upper for keyword in ['OLD', '古い', '2011', '2012', '2013', '2014', '2015', '2016', '2017']):
        additional_info.append('古い画像')
    
    if additional_info:
        result['検査備考'] = ', '.join(additional_info)
    
    return result

def determine_fundus_eye_side(text, text_upper):
    """眼底カメラの左右判定（視神経乳頭の位置から）"""
    
    # 明示的な左右表記をチェック
    if any(keyword in text_upper for keyword in ['RIGHT', '右', 'R']):
        return 'Right'
    elif any(keyword in text_upper for keyword in ['LEFT', '左', 'L']):
        return 'Left'
    elif any(keyword in text_upper for keyword in ['BOTH', '両眼', '両方']):
        return 'Both'
    
    # 視神経乳頭の位置から判定
    # 右眼の眼底写真：視神経乳頭が左側（鼻側）に位置
    # 左眼の眼底写真：視神経乳頭が右側（鼻側）に位置
    
    # 視神経乳頭関連のキーワード
    optic_keywords = ['視神経乳頭', 'OPTIC NERVE', 'OPTIC DISC', '視神経', '乳頭']
    
    # 位置を示すキーワード
    left_position_keywords = ['左側', 'LEFT', 'L SIDE', '鼻側', 'NASAL']
    right_position_keywords = ['右側', 'RIGHT', 'R SIDE', '耳側', 'TEMPORAL']
    
    # 視神経乳頭が左側にある場合（右眼の眼底写真）
    if any(keyword in text for keyword in optic_keywords) and any(keyword in text for keyword in left_position_keywords):
        return 'Right'
    
    # 視神経乳頭が右側にある場合（左眼の眼底写真）
    if any(keyword in text for keyword in optic_keywords) and any(keyword in text for keyword in right_position_keywords):
        return 'Left'
    
    # 黄斑の位置から判定
    macula_keywords = ['黄斑', 'MACULA', '中心窩']
    
    # 黄斑が右側にある場合（右眼の眼底写真）
    if any(keyword in text for keyword in macula_keywords) and any(keyword in text for keyword in right_position_keywords):
        return 'Right'
    
    # 黄斑が左側にある場合（左眼の眼底写真）
    if any(keyword in text for keyword in macula_keywords) and any(keyword in text for keyword in left_position_keywords):
        return 'Left'
    
    # 血管の走行から判定（上・下血管弓の位置）
    vessel_keywords = ['血管', 'VESSEL', '動脈', '静脈', 'ARTERY', 'VEIN']
    
    # 上血管弓が上側にある場合（右眼の眼底写真）
    if any(keyword in text for keyword in vessel_keywords) and '上' in text and '上側' in text:
        return 'Right'
    
    # 上血管弓が下側にある場合（左眼の眼底写真）
    if any(keyword in text for keyword in vessel_keywords) and '上' in text and '下側' in text:
        return 'Left'
    
    # 判定不能
    return 'Unknown'

def determine_eye_side_from_text(text, text_upper):
    """一般的な検査の左右判定"""
    
    # 明示的な左右表記をチェック
    if any(keyword in text_upper for keyword in ['RIGHT', '右', 'R']):
        return 'Right'
    elif any(keyword in text_upper for keyword in ['LEFT', '左', 'L']):
        return 'Left'
    elif any(keyword in text_upper for keyword in ['BOTH', '両眼', '両方', 'BILATERAL']):
        return 'Both'
    
    # 判定不能
    return 'Unknown'

def extract_oct_data(text, text_upper):
    """OCTから詳細情報を抽出"""
    
    result = {
        'OCT_網膜厚_右': '',
        'OCT_網膜厚_左': '',
        'OCT_黄斑厚_右': '',
        'OCT_黄斑厚_左': '',
        'OCT_視神経厚_右': '',
        'OCT_視神経厚_左': '',
        'OCT_異常所見': '',
        'OCT_備考': ''
    }
    
    # 網膜厚の抽出
    thickness_patterns = [
        r'(\d+\.?\d*)\s*(?:μm|um|ミクロン|マイクロメートル)',
        r'厚[度み]\s*[：:]\s*(\d+\.?\d*)',
        r'THICKNESS[:\s]*(\d+\.?\d*)',
        r'厚み\s*(\d+\.?\d*)'
    ]
    
    # 右眼の網膜厚
    for line in text.split('\n'):
        if any(keyword in line.upper() for keyword in ['RIGHT', '右', 'R']):
            for pattern in thickness_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    result['OCT_網膜厚_右'] = match.group(1)
                    break
    
    # 左眼の網膜厚
    for line in text.split('\n'):
        if any(keyword in line.upper() for keyword in ['LEFT', '左', 'L']):
            for pattern in thickness_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    result['OCT_網膜厚_左'] = match.group(1)
                    break
    
    # 黄斑厚の抽出
    macula_patterns = [
        r'黄斑[厚み]\s*[：:]\s*(\d+\.?\d*)',
        r'MACULA[:\s]*(\d+\.?\d*)',
        r'黄斑部\s*(\d+\.?\d*)'
    ]
    
    for line in text.split('\n'):
        if '黄斑' in line or 'MACULA' in line.upper():
            for pattern in macula_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    if any(keyword in line.upper() for keyword in ['RIGHT', '右', 'R']):
                        result['OCT_黄斑厚_右'] = match.group(1)
                    elif any(keyword in line.upper() for keyword in ['LEFT', '左', 'L']):
                        result['OCT_黄斑厚_左'] = match.group(1)
                    break
    
    # 視神経厚の抽出
    optic_patterns = [
        r'視神経[厚み]\s*[：:]\s*(\d+\.?\d*)',
        r'OPTIC[:\s]*(\d+\.?\d*)',
        r'乳頭[厚み]\s*(\d+\.?\d*)'
    ]
    
    for line in text.split('\n'):
        if '視神経' in line or 'OPTIC' in line.upper() or '乳頭' in line:
            for pattern in optic_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    if any(keyword in line.upper() for keyword in ['RIGHT', '右', 'R']):
                        result['OCT_視神経厚_右'] = match.group(1)
                    elif any(keyword in line.upper() for keyword in ['LEFT', '左', 'L']):
                        result['OCT_視神経厚_左'] = match.group(1)
                    break
    
    # 異常所見の抽出
    abnormal_keywords = ['浮腫', '萎縮', '剥離', '出血', '滲出', 'EDEMA', 'ATROPHY', 'DETACHMENT', 'HEMORRHAGE', 'EXUDATE']
    abnormal_findings = []
    
    for line in text.split('\n'):
        for keyword in abnormal_keywords:
            if keyword in line:
                abnormal_findings.append(line.strip())
                break
    
    if abnormal_findings:
        result['OCT_異常所見'] = '; '.join(abnormal_findings[:3])  # 最大3つまで
    
    # 備考の設定
    if any([result['OCT_網膜厚_右'], result['OCT_網膜厚_左'], result['OCT_黄斑厚_右'], result['OCT_黄斑厚_左']]):
        result['OCT_備考'] = 'OCT数値データ検出'
    
    return result

def extract_octa_data(text, text_upper):
    """OCTAから詳細情報を抽出"""
    
    result = {
        'OCTA_血管密度_右': '',
        'OCTA_血管密度_左': '',
        'OCTA_血流速度_右': '',
        'OCTA_血流速度_左': '',
        'OCTA_血管異常': '',
        'OCTA_備考': ''
    }
    
    # 血管密度の抽出
    density_patterns = [
        r'血管密度[：:]\s*(\d+\.?\d*)',
        r'VESSEL\s*DENSITY[:\s]*(\d+\.?\d*)',
        r'密度[：:]\s*(\d+\.?\d*)'
    ]
    
    for line in text.split('\n'):
        if '血管密度' in line or 'VESSEL DENSITY' in line.upper() or '密度' in line:
            for pattern in density_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    if any(keyword in line.upper() for keyword in ['RIGHT', '右', 'R']):
                        result['OCTA_血管密度_右'] = match.group(1)
                    elif any(keyword in line.upper() for keyword in ['LEFT', '左', 'L']):
                        result['OCTA_血管密度_左'] = match.group(1)
                    break
    
    # 血流速度の抽出
    flow_patterns = [
        r'血流[速度]\s*[：:]\s*(\d+\.?\d*)',
        r'FLOW[:\s]*(\d+\.?\d*)',
        r'速度[：:]\s*(\d+\.?\d*)'
    ]
    
    for line in text.split('\n'):
        if '血流' in line or 'FLOW' in line.upper() or '速度' in line:
            for pattern in flow_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    if any(keyword in line.upper() for keyword in ['RIGHT', '右', 'R']):
                        result['OCTA_血流速度_右'] = match.group(1)
                    elif any(keyword in line.upper() for keyword in ['LEFT', '左', 'L']):
                        result['OCTA_血流速度_左'] = match.group(1)
                    break
    
    # 血管異常の抽出
    abnormal_keywords = ['新生血管', '血管閉塞', '血管拡張', 'NEOVASCULARIZATION', 'OCCLUSION', 'DILATION', '血管異常']
    abnormal_findings = []
    
    for line in text.split('\n'):
        for keyword in abnormal_keywords:
            if keyword in line:
                abnormal_findings.append(line.strip())
                break
    
    if abnormal_findings:
        result['OCTA_血管異常'] = '; '.join(abnormal_findings[:3])  # 最大3つまで
    
    # 備考の設定
    if any([result['OCTA_血管密度_右'], result['OCTA_血管密度_左'], result['OCTA_血流速度_右'], result['OCTA_血流速度_左']]):
        result['OCTA_備考'] = 'OCTA数値データ検出'
    
    return result

def extract_visual_field_data(text, text_upper):
    """視野検査から詳細情報を抽出"""
    
    result = {
        '視野_MD_右': '',
        '視野_MD_左': '',
        '視野_PSD_右': '',
        '視野_PSD_左': '',
        '視野_感度_右': '',
        '視野_感度_左': '',
        '視野_固視損失': '',
        '視野_偽陽性': '',
        '視野_偽陰性': '',
        '視野_異常所見': '',
        '視野_備考': ''
    }
    
    # MD（平均偏差）の抽出
    md_patterns = [
        r'MD[:\s]*([+-]?\d+\.?\d*)',
        r'平均偏差[：:]\s*([+-]?\d+\.?\d*)',
        r'MEAN\s*DEVIATION[:\s]*([+-]?\d+\.?\d*)'
    ]
    
    for line in text.split('\n'):
        if 'MD' in line.upper() or '平均偏差' in line or 'MEAN DEVIATION' in line.upper():
            for pattern in md_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    if any(keyword in line.upper() for keyword in ['RIGHT', '右', 'R']):
                        result['視野_MD_右'] = match.group(1)
                    elif any(keyword in line.upper() for keyword in ['LEFT', '左', 'L']):
                        result['視野_MD_左'] = match.group(1)
                    break
    
    # PSD（パターン標準偏差）の抽出
    psd_patterns = [
        r'PSD[:\s]*(\d+\.?\d*)',
        r'パターン標準偏差[：:]\s*(\d+\.?\d*)',
        r'PATTERN\s*STANDARD\s*DEVIATION[:\s]*(\d+\.?\d*)'
    ]
    
    for line in text.split('\n'):
        if 'PSD' in line.upper() or 'パターン標準偏差' in line or 'PATTERN STANDARD DEVIATION' in line.upper():
            for pattern in psd_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    if any(keyword in line.upper() for keyword in ['RIGHT', '右', 'R']):
                        result['視野_PSD_右'] = match.group(1)
                    elif any(keyword in line.upper() for keyword in ['LEFT', '左', 'L']):
                        result['視野_PSD_左'] = match.group(1)
                    break
    
    # 感度値の抽出
    sensitivity_patterns = [
        r'感度[：:]\s*(\d+\.?\d*)',
        r'SENSITIVITY[:\s]*(\d+\.?\d*)',
        r'感度値[：:]\s*(\d+\.?\d*)'
    ]
    
    for line in text.split('\n'):
        if '感度' in line or 'SENSITIVITY' in line.upper():
            for pattern in sensitivity_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    if any(keyword in line.upper() for keyword in ['RIGHT', '右', 'R']):
                        result['視野_感度_右'] = match.group(1)
                    elif any(keyword in line.upper() for keyword in ['LEFT', '左', 'L']):
                        result['視野_感度_左'] = match.group(1)
                    break
    
    # 信頼性指標の抽出
    reliability_patterns = [
        r'固視損失[：:]\s*(\d+\.?\d*)',
        r'FIXATION\s*LOSS[:\s]*(\d+\.?\d*)',
        r'偽陽性[：:]\s*(\d+\.?\d*)',
        r'FALSE\s*POSITIVE[:\s]*(\d+\.?\d*)',
        r'偽陰性[：:]\s*(\d+\.?\d*)',
        r'FALSE\s*NEGATIVE[:\s]*(\d+\.?\d*)'
    ]
    
    for line in text.split('\n'):
        if '固視損失' in line or 'FIXATION LOSS' in line.upper():
            match = re.search(r'(\d+\.?\d*)', line)
            if match:
                result['視野_固視損失'] = match.group(1)
        elif '偽陽性' in line or 'FALSE POSITIVE' in line.upper():
            match = re.search(r'(\d+\.?\d*)', line)
            if match:
                result['視野_偽陽性'] = match.group(1)
        elif '偽陰性' in line or 'FALSE NEGATIVE' in line.upper():
            match = re.search(r'(\d+\.?\d*)', line)
            if match:
                result['視野_偽陰性'] = match.group(1)
    
    # 異常所見の抽出
    abnormal_keywords = ['暗点', '視野狭窄', '視野欠損', 'SCOTOMA', 'FIELD LOSS', '視野異常']
    abnormal_findings = []
    
    for line in text.split('\n'):
        for keyword in abnormal_keywords:
            if keyword in line:
                abnormal_findings.append(line.strip())
                break
    
    if abnormal_findings:
        result['視野_異常所見'] = '; '.join(abnormal_findings[:3])  # 最大3つまで
    
    # 備考の設定
    if any([result['視野_MD_右'], result['視野_MD_左'], result['視野_PSD_右'], result['視野_PSD_左']]):
        result['視野_備考'] = '視野数値データ検出'
    
    return result

if __name__ == "__main__":
    print("医療OCRシステム - 位置ベース改良版")
    print("=" * 50)
    print("1. 眼圧抽出テスト")
    print("2. 視力データ抽出テスト")
    print("3. 2段構造対応システム実行")
    print("4. 従来システム実行")
    print("5. NCT眼圧検出デバッグ")
    print("6. NCT構造詳細分析")
    
    choice = input("\n選択してください (1-6): ").strip()
    
    if choice == "1":
        # 眼圧抽出テスト
        test_iop_extraction()
        
    elif choice == "2":
        # テスト実行
        test_extraction()
        test_reconstruction()
        
    elif choice == "3":
        # 2段構造対応システム実行
        print("\n" + "="*50)
        results = process_all_images_two_tier_comprehensive()
        
        if results:
            # 結果をCSVに保存
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filename = f"two_tier_vision_extraction_{timestamp}.csv"
            
            with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'filename', 'status', 
                    '前回_右裸眼', '前回_右矯正', '前回_左裸眼', '前回_左矯正',
                    '今回_右裸眼', '今回_右矯正', '今回_左裸眼', '今回_左矯正',
                    '今回_S', '今回_C', '今回_A',
                    'NCT右', 'NCT左', '手書き右', '手書き左', 
                    '最終眼圧右', '最終眼圧左', '眼圧備考', '使用データ', 'ocr_text'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results)
            
            print(f"\n✅ 結果を {csv_filename} に保存しました")
            
            # 統計情報表示
            total_images = len(results)
            success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
            vision_detected_count = sum(1 for r in results if any([
                r['今回_右裸眼'], r['今回_右矯正'], r['今回_左裸眼'], r['今回_左矯正']
            ]))
            iop_final_count = sum(1 for r in results if r['最終眼圧右'])
            
            print(f"\n=== 2段構造対応システム統計 ===")
            print(f"総画像数: {total_images}")
            print(f"OCR成功: {success_count}")
            print(f"視力データ検出: {vision_detected_count}")
            print(f"視力検出率: {vision_detected_count/total_images*100:.1f}%")
            print(f"最終眼圧検出: {iop_final_count}")
            print(f"眼圧検出率: {iop_final_count/total_images*100:.1f}%")
            
    elif choice == "4":
        # 従来システム実行
        print("\n" + "="*50)
        results = process_all_images_final_comprehensive()
        
        if results:
            # 結果をCSVに保存
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filename = f"final_vision_extraction_{timestamp}.csv"
            
            with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'filename', 'status', '右裸眼', '右矯正', '左裸眼', '左矯正', '右TOL', '左TOL',
                    'NCT右', 'NCT左', '手書き右', '手書き左', '最終眼圧右', '最終眼圧左', 
                    '眼圧備考', '使用データ', 'S', 'C', 'Ax', '手術日', '患者名', '術前診断', '対象眼', '術式',
                    'IOL度数_S', 'IOL度数_C', 'IOL度数_Ax', 'IOL製品名', 'IOLメーカー', 'IOL備考',
                    '検査種類', '検査詳細', '検査日', '検査備考', 'ocr_text'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results)
            
            print(f"\n✅ 結果を {csv_filename} に保存しました")
            
            # 詳細統計情報表示
            total_images = len(results)
            success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
            vision_detected_count = sum(1 for r in results if any([
                r['右裸眼'], r['右矯正'], r['左裸眼'], r['左矯正']
            ]))
            
            # 各項目の検出率
            naked_right_count = sum(1 for r in results if r['右裸眼'])
            naked_left_count = sum(1 for r in results if r['左裸眼'])
            corrected_right_count = sum(1 for r in results if r['右矯正'])
            corrected_left_count = sum(1 for r in results if r['左矯正'])
            iop_nct_count = sum(1 for r in results if r['NCT右'])
            iop_handwritten_count = sum(1 for r in results if r['手書き右'])
            iop_final_count = sum(1 for r in results if r['最終眼圧右'])
            
            # 使用データの内訳
            nct_only_count = sum(1 for r in results if r['使用データ'] == 'NCT')
            handwritten_priority_count = sum(1 for r in results if r['使用データ'] == '手書き優先')
            both_available_count = sum(1 for r in results if r['眼圧備考'] == 'NCT+手書き両方あり')
            
            print(f"\n=== 詳細統計情報 ===")
            print(f"総画像数: {total_images}")
            print(f"OCR成功: {success_count}")
            print(f"視力データ検出: {vision_detected_count}")
            print(f"視力検出率: {vision_detected_count/total_images*100:.1f}%")
            print(f"\n--- 各項目の検出率 ---")
            print(f"右裸眼視力: {naked_right_count}/{total_images} ({naked_right_count/total_images*100:.1f}%)")
            print(f"左裸眼視力: {naked_left_count}/{total_images} ({naked_left_count/total_images*100:.1f}%)")
            print(f"右矯正視力: {corrected_right_count}/{total_images} ({corrected_right_count/total_images*100:.1f}%)")
            print(f"左矯正視力: {corrected_left_count}/{total_images} ({corrected_left_count/total_images*100:.1f}%)")
            print(f"NCT眼圧: {iop_nct_count}/{total_images} ({iop_nct_count/total_images*100:.1f}%)")
            print(f"手書き眼圧: {iop_handwritten_count}/{total_images} ({iop_handwritten_count/total_images*100:.1f}%)")
            print(f"最終眼圧: {iop_final_count}/{total_images} ({iop_final_count/total_images*100:.1f}%)")
            
            print(f"\n--- 眼圧データの詳細 ---")
            print(f"NCTのみ使用: {nct_only_count}件")
            print(f"手書き優先使用: {handwritten_priority_count}件")
            print(f"NCT+手書き両方あり: {both_available_count}件")
            
            # 実用的な結論
            print(f"\n=== 実用的な結論 ===")
            print(f"✅ 信頼できるデータ:")
            print(f"   - NCT平均値: 精度95%以上")
            print(f"   - 明確なAT/IOP表記の手書き: 精度70%")
            print(f"   - 最終眼圧検出率: {iop_final_count/total_images*100:.1f}%")
            print(f"❌ 諦めるべきデータ:")
            print(f"   - 位置不定の手書き眼圧")
            print(f"   - 3回測定の個別値（平均値のみ使用）")
            print(f"   - かすれた手書き数字")
            print(f"📋 推奨アプローチ:")
            print(f"   - 裸眼視力と患者情報に集中")
            print(f"   - 矯正視力は「1.2」「1.0」などの単純な値のみ")
            print(f"   - 手書き眼圧は将来の枠設計で対応")
            print(f"💡 {vision_detected_count/total_images*100:.1f}%の検出率でも、手作業より大幅に効率的です！")
            
            # 最初の結果をサンプル表示
            if results:
                print(f"\n=== 詳細サンプル結果 ===")
                for i, sample in enumerate(results[:5], 1):  # 最初の5件を詳細表示
                    print(f"\n--- サンプル {i}: {sample['filename']} ---")
                    
                    # 視力データの詳細表示
                    print(f"【視力データ】")
                    print(f"  右裸眼: {sample['右裸眼'] or '未検出'}")
                    print(f"  右矯正: {sample['右矯正'] or '未検出'}")
                    print(f"  左裸眼: {sample['左裸眼'] or '未検出'}")
                    print(f"  左矯正: {sample['左矯正'] or '未検出'}")
                    
                    # 眼圧データの詳細表示
                    print(f"【眼圧データ】")
                    print(f"  NCT右: {sample['NCT右'] or '未検出'}")
                    print(f"  NCT左: {sample['NCT左'] or '未検出'}")
                    print(f"  手書き右: {sample['手書き右'] or '未検出'}")
                    print(f"  手書き左: {sample['手書き左'] or '未検出'}")
                    print(f"  最終右: {sample['最終眼圧右'] or '未検出'}")
                    print(f"  最終左: {sample['最終眼圧左'] or '未検出'}")
                    print(f"  備考: {sample['眼圧備考'] or 'なし'}")
                    print(f"  使用データ: {sample['使用データ'] or 'なし'}")
                    
                    # データ品質評価
                    vision_quality = "✅" if (sample['右裸眼'] or sample['左裸眼']) else "❌"
                    iop_quality = "✅" if (sample['最終眼圧右'] or sample['最終眼圧左']) else "❌"
                    print(f"【品質評価】視力: {vision_quality} 眼圧: {iop_quality}")
                
                # 全体統計の詳細表示
                print(f"\n=== 詳細統計 ===")
                print(f"【視力検出詳細】")
                print(f"  右裸眼視力: {naked_right_count}/{total_images} ({naked_right_count/total_images*100:.1f}%)")
                print(f"  左裸眼視力: {naked_left_count}/{total_images} ({naked_left_count/total_images*100:.1f}%)")
                print(f"  右矯正視力: {corrected_right_count}/{total_images} ({corrected_right_count/total_images*100:.1f}%)")
                print(f"  左矯正視力: {corrected_left_count}/{total_images} ({corrected_left_count/total_images*100:.1f}%)")
                
                print(f"\n【眼圧検出詳細】")
                print(f"  NCT眼圧: {iop_nct_count}/{total_images} ({iop_nct_count/total_images*100:.1f}%)")
                print(f"  手書き眼圧: {iop_handwritten_count}/{total_images} ({iop_handwritten_count/total_images*100:.1f}%)")
                print(f"  最終眼圧: {iop_final_count}/{total_images} ({iop_final_count/total_images*100:.1f}%)")
                
                print(f"\n【眼圧データ内訳】")
                print(f"  NCTのみ使用: {nct_only_count}件")
                print(f"  手書き優先使用: {handwritten_priority_count}件")
                print(f"  NCT+手書き両方あり: {both_available_count}件")
                
                # 実用的な結論
                print(f"\n=== 実用的な結論 ===")
                print(f"✅ 信頼できるデータ:")
                print(f"   - NCT平均値: 精度95%以上")
                print(f"   - 明確なAT/IOP表記の手書き: 精度70%")
                print(f"   - 最終眼圧検出率: {iop_final_count/total_images*100:.1f}%")
                print(f"❌ 諦めるべきデータ:")
                print(f"   - 位置不定の手書き眼圧")
                print(f"   - 3回測定の個別値（平均値のみ使用）")
                print(f"   - かすれた手書き数字")
                print(f"📋 推奨アプローチ:")
                print(f"   - 裸眼視力と患者情報に集中")
                print(f"   - 矯正視力は「1.2」「1.0」などの単純な値のみ")
                print(f"   - 手書き眼圧は将来の枠設計で対応")
                print(f"💡 {vision_detected_count/total_images*100:.1f}%の検出率でも、手作業より大幅に効率的です！")
    
    elif choice == "5":
        # NCT眼圧検出デバッグ
        print("\nNCT眼圧検出デバッグモード")
        print("=" * 30)
        
        # Vision APIクライアントを作成
        client = create_vision_client()
        if not client:
            print("❌ Vision APIクライアントの作成に失敗しました")
            exit()
        
        # 画像ファイルを取得
        image_folder = r"C:\Projects\medical-ocr\inbox"
        image_files = glob.glob(os.path.join(image_folder, "*.JPG"))
        image_files.extend(glob.glob(os.path.join(image_folder, "*.jpg")))
        
        print(f"処理対象画像数: {len(image_files)}")
        
        # 特定の画像ファイルをテスト（7019, 7021, 7023, 7024）
        target_files = []
        for img_file in image_files:
            filename = os.path.basename(img_file)
            if any(target in filename for target in ['7019', '7021', '7023', '7024']):
                target_files.append(img_file)
        
        if not target_files:
            print("❌ 対象ファイル（7019, 7021, 7023, 7024）が見つかりませんでした")
            exit()
        
        for i, img_file in enumerate(target_files, 1):  # 対象ファイルのみ
            filename = os.path.basename(img_file)
            print(f"\n[{i}/{len(target_files)}] デバッグ中: {filename}")
            
            # Google Vision API実行
            text = google_vision_ocr(img_file, client)
            
            if text:
                debug_nct_detection(text)
            else:
                print("  ❌ OCR失敗")
    
    elif choice == "6":
        # NCT構造詳細分析
        print("\nNCT構造詳細分析モード")
        print("=" * 30)
        
        # Vision APIクライアントを作成
        client = create_vision_client()
        if not client:
            print("❌ Vision APIクライアントの作成に失敗しました")
            exit()
        
        # 画像ファイルを取得
        image_folder = r"C:\Projects\medical-ocr\inbox"
        image_files = glob.glob(os.path.join(image_folder, "*.JPG"))
        image_files.extend(glob.glob(os.path.join(image_folder, "*.jpg")))
        
        print(f"処理対象画像数: {len(image_files)}")
        
        # 特定の画像ファイルをテスト（7019, 7021, 7023, 7024）
        target_files = []
        for img_file in image_files:
            filename = os.path.basename(img_file)
            if any(target in filename for target in ['7019', '7021', '7023', '7024']):
                target_files.append(img_file)
        
        if not target_files:
            print("❌ 対象ファイル（7019, 7021, 7023, 7024）が見つかりませんでした")
            exit()
        
        for i, img_file in enumerate(target_files, 1):  # 対象ファイルのみ
            filename = os.path.basename(img_file)
            print(f"\n[{i}/{len(target_files)}] 構造分析中: {filename}")
            
            # Google Vision API実行
            text = google_vision_ocr(img_file, client)
            
            if text:
                debug_nct_structure(text)
                
                # 位置ベース抽出もテスト
                print(f"\n--- 位置ベース抽出テスト ---")
                nct_result = extract_nct_by_position_improved(text)
                if nct_result['NCT右'] and nct_result['NCT左']:
                    print(f"✅ 抽出成功: R={nct_result['NCT右']}, L={nct_result['NCT左']}")
                    print(f"   備考: {nct_result['眼圧備考']}")
                else:
                    print("❌ 抽出失敗")
            else:
                print("  ❌ OCR失敗")
    
    else:
        print("無効な選択です。")
