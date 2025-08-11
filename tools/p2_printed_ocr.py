# -*- coding: utf-8 -*-
"""
P2: 印刷系OCR - NCT・レフ値・IOLシール抽出
対象項目:
- NCT平均値: Avg. 13.7 / 14.0（右/左）≥98%
- レフ値: S/C/Ax（例: -3.00/-0.75/180）誤差≤±0.25D
- IOLシール: 度数（+20.0D）・製品名 正確な読取

使い方:
  ドライラン: python p2_printed_ocr.py --patients-root ".\Patients" --master-csv ".\Patients\master.csv"
  本適用 　: python p2_printed_ocr.py --patients-root ".\Patients" --master-csv ".\Patients\master.csv" --apply
"""

import argparse
import csv
import os
import re
import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import logging

import numpy as np
import cv2
from PIL import Image
import easyocr
from google.cloud import vision
from google.oauth2 import service_account

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class NCTResult:
    """NCT測定結果"""
    right_eye: Optional[float] = None
    left_eye: Optional[float] = None
    confidence: float = 0.0
    qa_flag: str = ""

@dataclass
class RefractionResult:
    """レフ値測定結果"""
    sphere: Optional[float] = None      # S値
    cylinder: Optional[float] = None    # C値
    axis: Optional[int] = None          # Ax値
    confidence: float = 0.0
    qa_flag: str = ""

@dataclass
class IOLSealResult:
    """IOLシール情報"""
    power: Optional[float] = None       # 度数
    product_name: Optional[str] = None  # 製品名
    confidence: float = 0.0
    qa_flag: str = ""

@dataclass
class P2OCRResult:
    """P2 OCR結果"""
    nct: NCTResult
    refraction: RefractionResult
    iol_seal: IOLSealResult
    overall_confidence: float = 0.0
    processing_time: float = 0.0

class P2PrintedOCR:
    """印刷系OCR処理クラス"""
    
    def __init__(self, api_key: str = None, use_gpu: bool = False):
        self.api_key = api_key
        self.use_gpu = use_gpu
        
        # EasyOCR初期化
        self.reader = easyocr.Reader(['ja', 'en'], gpu=use_gpu)
        
        # Google Vision API初期化（APIキーがある場合）
        self.vision_client = None
        if api_key:
            try:
                credentials = service_account.Credentials.from_service_account_file(api_key)
                self.vision_client = vision.ImageAnnotatorClient(credentials=credentials)
            except Exception as e:
                logger.warning(f"Google Vision API初期化失敗: {e}")
        
        # 正規表現パターン
        self.nct_patterns = [
            r'NCT[:\s]*([0-9]+\.?[0-9]*)\s*/\s*([0-9]+\.?[0-9]*)',  # NCT: 13.7 / 14.0
            r'眼圧[:\s]*([0-9]+\.?[0-9]*)\s*/\s*([0-9]+\.?[0-9]*)',  # 眼圧: 13.7 / 14.0
            r'([0-9]+\.?[0-9]*)\s*/\s*([0-9]+\.?[0-9]*)\s*mmHg',     # 13.7 / 14.0 mmHg
            r'右[:\s]*([0-9]+\.?[0-9]*)\s*左[:\s]*([0-9]+\.?[0-9]*)', # 右: 13.7 左: 14.0
        ]
        
        self.refraction_patterns = [
            r'([+-]?[0-9]+\.?[0-9]*)\s*/\s*([+-]?[0-9]+\.?[0-9]*)\s*/\s*([0-9]+)',  # -3.00/-0.75/180
            r'S[:\s]*([+-]?[0-9]+\.?[0-9]*)\s*C[:\s]*([+-]?[0-9]+\.?[0-9]*)\s*Ax[:\s]*([0-9]+)',  # S: -3.00 C: -0.75 Ax: 180
            r'球面[:\s]*([+-]?[0-9]+\.?[0-9]*)\s*円柱[:\s]*([+-]?[0-9]+\.?[0-9]*)\s*軸[:\s]*([0-9]+)',  # 球面: -3.00 円柱: -0.75 軸: 180
        ]
        
        self.iol_patterns = [
            r'IOL[:\s]*([+-]?[0-9]+\.?[0-9]*)D',  # IOL: +20.0D
            r'度数[:\s]*([+-]?[0-9]+\.?[0-9]*)D',  # 度数: +20.0D
            r'([+-]?[0-9]+\.?[0-9]*)D\s*([A-Za-z0-9\s\-]+)',  # +20.0D 製品名
        ]
        
        # 製品名辞書
        self.iol_products = [
            'Alcon', 'AMO', 'Johnson & Johnson', 'J&J', 'Zeiss', 'HOYA', 'Rayner',
            'AcrySof', 'Tecnis', 'Clareon', 'enVista', 'iSert', 'AT LARA',
            'AT TORBI', 'AT LISA', 'AT LARA', 'AT TORBI', 'AT LISA'
        ]

    def extract_text_from_image(self, image_path: Path) -> List[Dict[str, Any]]:
        """画像からテキスト抽出"""
        results = []
        
        try:
            # EasyOCRでテキスト抽出
            easyocr_results = self.reader.readtext(str(image_path))
            for (bbox, text, confidence) in easyocr_results:
                results.append({
                    'text': text,
                    'confidence': confidence,
                    'bbox': bbox,
                    'source': 'easyocr'
                })
            
            # Google Vision API（利用可能な場合）
            if self.vision_client:
                try:
                    with open(image_path, 'rb') as image_file:
                        content = image_file.read()
                    
                    image = vision.Image(content=content)
                    response = self.vision_client.text_detection(image=image)
                    
                    if response.text_annotations:
                        for annotation in response.text_annotations[1:]:  # 最初は全体テキストなのでスキップ
                            vertices = [(vertex.x, vertex.y) for vertex in annotation.bounding_poly.vertices]
                            results.append({
                                'text': annotation.description,
                                'confidence': 0.9,  # Google Visionは信頼度を返さないので固定値
                                'bbox': vertices,
                                'source': 'google_vision'
                            })
                except Exception as e:
                    logger.warning(f"Google Vision API処理失敗: {e}")
                    
        except Exception as e:
            logger.error(f"テキスト抽出失敗 {image_path}: {e}")
        
        return results

    def extract_nct_values(self, text_results: List[Dict[str, Any]]) -> NCTResult:
        """NCT値を抽出"""
        all_text = ' '.join([r['text'] for r in text_results])
        
        for pattern in self.nct_patterns:
            match = re.search(pattern, all_text, re.IGNORECASE)
            if match:
                try:
                    right_val = float(match.group(1))
                    left_val = float(match.group(2))
                    
                    # 妥当性チェック
                    if 5.0 <= right_val <= 50.0 and 5.0 <= left_val <= 50.0:
                        confidence = np.mean([r['confidence'] for r in text_results if match.group(0) in r['text']])
                        qa_flag = "OK" if confidence >= 0.8 else "LOW_CONF"
                        
                        return NCTResult(
                            right_eye=right_val,
                            left_eye=left_val,
                            confidence=confidence,
                            qa_flag=qa_flag
                        )
                except (ValueError, IndexError):
                    continue
        
        return NCTResult(qa_flag="NOT_FOUND")

    def extract_refraction_values(self, text_results: List[Dict[str, Any]]) -> RefractionResult:
        """レフ値を抽出"""
        all_text = ' '.join([r['text'] for r in text_results])
        
        for pattern in self.refraction_patterns:
            match = re.search(pattern, all_text, re.IGNORECASE)
            if match:
                try:
                    sphere = float(match.group(1))
                    cylinder = float(match.group(2))
                    axis = int(match.group(3))
                    
                    # 妥当性チェック
                    if (-20.0 <= sphere <= 20.0 and 
                        -6.0 <= cylinder <= 6.0 and 
                        0 <= axis <= 180):
                        
                        confidence = np.mean([r['confidence'] for r in text_results if match.group(0) in r['text']])
                        qa_flag = "OK" if confidence >= 0.8 else "LOW_CONF"
                        
                        return RefractionResult(
                            sphere=sphere,
                            cylinder=cylinder,
                            axis=axis,
                            confidence=confidence,
                            qa_flag=qa_flag
                        )
                except (ValueError, IndexError):
                    continue
        
        return RefractionResult(qa_flag="NOT_FOUND")

    def extract_iol_seal_info(self, text_results: List[Dict[str, Any]]) -> IOLSealResult:
        """IOLシール情報を抽出"""
        all_text = ' '.join([r['text'] for r in text_results])
        
        # 度数抽出
        power = None
        for pattern in self.iol_patterns:
            match = re.search(pattern, all_text, re.IGNORECASE)
            if match:
                try:
                    power = float(match.group(1))
                    if -30.0 <= power <= 30.0:
                        break
                except (ValueError, IndexError):
                    continue
        
        # 製品名抽出
        product_name = None
        for product in self.iol_products:
            if product.lower() in all_text.lower():
                product_name = product
                break
        
        if power is not None or product_name is not None:
            confidence = np.mean([r['confidence'] for r in text_results])
            qa_flag = "OK" if confidence >= 0.8 else "LOW_CONF"
            
            return IOLSealResult(
                power=power,
                product_name=product_name,
                confidence=confidence,
                qa_flag=qa_flag
            )
        
        return IOLSealResult(qa_flag="NOT_FOUND")

    def process_image(self, image_path: Path) -> P2OCRResult:
        """画像を処理してP2 OCR結果を取得"""
        import time
        start_time = time.time()
        
        # テキスト抽出
        text_results = self.extract_text_from_image(image_path)
        
        # 各項目抽出
        nct_result = self.extract_nct_values(text_results)
        refraction_result = self.extract_refraction_values(text_results)
        iol_result = self.extract_iol_seal_info(text_results)
        
        # 全体信頼度計算
        confidences = [
            nct_result.confidence,
            refraction_result.confidence,
            iol_result.confidence
        ]
        overall_confidence = np.mean([c for c in confidences if c > 0])
        
        processing_time = time.time() - start_time
        
        return P2OCRResult(
            nct=nct_result,
            refraction=refraction_result,
            iol_seal=iol_result,
            overall_confidence=overall_confidence,
            processing_time=processing_time
        )

def main():
    parser = argparse.ArgumentParser(description='P2: 印刷系OCR - NCT・レフ値・IOLシール抽出')
    parser.add_argument('--patients-root', required=True, help='患者データルートディレクトリ')
    parser.add_argument('--master-csv', required=True, help='マスターCSVファイル')
    parser.add_argument('--api-key', help='Google Vision APIキーファイル')
    parser.add_argument('--apply', action='store_true', help='実際にCSVを更新する')
    parser.add_argument('--gpu', action='store_true', help='GPU使用')
    parser.add_argument('--limit', type=int, help='処理件数制限（テスト用）')
    
    args = parser.parse_args()
    
    # OCR初期化
    ocr = P2PrintedOCR(api_key=args.api_key, use_gpu=args.gpu)
    
    # マスターCSV読み込み
    master_path = Path(args.master_csv)
    if not master_path.exists():
        logger.error(f"マスターCSVが見つかりません: {master_path}")
        return
    
    patients_root = Path(args.patients_root)
    if not patients_root.exists():
        logger.error(f"患者データルートが見つかりません: {patients_root}")
        return
    
    # CSV処理
    processed_count = 0
    success_count = 0
    
    with open(master_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    for row in rows:
        if args.limit and processed_count >= args.limit:
            break
            
        # P2項目が既に存在する場合はスキップ
        if row.get('nct_right') and row.get('nct_left') and row.get('refraction_s') and row.get('iol_power'):
            continue
        
        # 画像パス構築
        patient_id = row.get('patient_id')
        visit_date = row.get('visit_date')
        image_name = row.get('image_name')
        
        if not all([patient_id, visit_date, image_name]):
            continue
        
        image_path = patients_root / patient_id / visit_date / 'raw' / image_name
        if not image_path.exists():
            continue
        
        logger.info(f"処理中: {image_path}")
        
        try:
            # OCR処理
            result = ocr.process_image(image_path)
            
            # 結果をCSV行に反映
            if result.nct.right_eye is not None:
                row['nct_right'] = result.nct.right_eye
                row['nct_right_confidence'] = result.nct.confidence
                row['nct_right_qa_flag'] = result.nct.qa_flag
            
            if result.nct.left_eye is not None:
                row['nct_left'] = result.nct.left_eye
                row['nct_left_confidence'] = result.nct.confidence
                row['nct_left_qa_flag'] = result.nct.qa_flag
            
            if result.refraction.sphere is not None:
                row['refraction_s'] = result.refraction.sphere
                row['refraction_c'] = result.refraction.cylinder
                row['refraction_ax'] = result.refraction.axis
                row['refraction_confidence'] = result.refraction.confidence
                row['refraction_qa_flag'] = result.refraction.qa_flag
            
            if result.iol_seal.power is not None:
                row['iol_power'] = result.iol_seal.power
                row['iol_product'] = result.iol_seal.product_name
                row['iol_confidence'] = result.iol_seal.confidence
                row['iol_qa_flag'] = result.iol_seal.qa_flag
            
            row['p2_processing_time'] = result.processing_time
            row['p2_overall_confidence'] = result.overall_confidence
            
            success_count += 1
            logger.info(f"成功: NCT右={result.nct.right_eye}, 左={result.nct.left_eye}, "
                       f"レフS={result.refraction.sphere}, IOL={result.iol_seal.power}")
            
        except Exception as e:
            logger.error(f"処理失敗 {image_path}: {e}")
            row['p2_error'] = str(e)
        
        processed_count += 1
    
    # 結果保存
    if args.apply:
        with open(master_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        logger.info(f"CSV更新完了: 処理={processed_count}, 成功={success_count}")
    else:
        logger.info(f"ドライラン完了: 処理={processed_count}, 成功={success_count}")

if __name__ == '__main__':
    main()
