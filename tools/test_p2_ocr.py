# -*- coding: utf-8 -*-
"""
P2 OCR テストスクリプト
- サンプルデータでの精度検証
- 合格基準チェック
- エラーケーステスト
"""

import sys
from pathlib import Path
import json
from typing import Dict, List, Tuple, Any
import logging

# P2 OCRモジュールをインポート
sys.path.append(str(Path(__file__).parent))
from p2_printed_ocr import P2PrintedOCR, NCTResult, RefractionResult, IOLSealResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class P2OCRTestSuite:
    """P2 OCRテストスイート"""
    
    def __init__(self):
        self.ocr = P2PrintedOCR(use_gpu=False)
        
        # テストケース定義
        self.test_cases = {
            'nct': [
                {
                    'text': 'NCT: 13.7 / 14.0',
                    'expected': {'right': 13.7, 'left': 14.0}
                },
                {
                    'text': '眼圧: 15.2 / 16.8 mmHg',
                    'expected': {'right': 15.2, 'left': 16.8}
                },
                {
                    'text': '右: 12.5 左: 13.1',
                    'expected': {'right': 12.5, 'left': 13.1}
                }
            ],
            'refraction': [
                {
                    'text': '-3.00/-0.75/180',
                    'expected': {'sphere': -3.00, 'cylinder': -0.75, 'axis': 180}
                },
                {
                    'text': 'S: +2.50 C: -1.25 Ax: 90',
                    'expected': {'sphere': 2.50, 'cylinder': -1.25, 'axis': 90}
                },
                {
                    'text': '球面: -1.75 円柱: -0.50 軸: 135',
                    'expected': {'sphere': -1.75, 'cylinder': -0.50, 'axis': 135}
                }
            ],
            'iol': [
                {
                    'text': 'IOL: +20.0D Alcon AcrySof',
                    'expected': {'power': 20.0, 'product': 'Alcon'}
                },
                {
                    'text': '度数: +18.5D Tecnis',
                    'expected': {'power': 18.5, 'product': 'Tecnis'}
                },
                {
                    'text': '+22.0D AT LARA',
                    'expected': {'power': 22.0, 'product': 'AT LARA'}
                }
            ]
        }
    
    def test_nct_extraction(self) -> Dict[str, float]:
        """NCT抽出テスト"""
        results = {'total': 0, 'success': 0, 'accuracy': 0.0}
        
        for case in self.test_cases['nct']:
            results['total'] += 1
            
            # テキスト結果を模擬
            text_results = [{'text': case['text'], 'confidence': 0.9, 'bbox': [], 'source': 'test'}]
            
            # NCT抽出実行
            nct_result = self.ocr.extract_nct_values(text_results)
            
            # 結果検証
            if (nct_result.right_eye == case['expected']['right'] and 
                nct_result.left_eye == case['expected']['left'] and
                nct_result.qa_flag == "OK"):
                results['success'] += 1
                logger.info(f"NCTテスト成功: {case['text']} -> 右:{nct_result.right_eye}, 左:{nct_result.left_eye}")
            else:
                logger.error(f"NCTテスト失敗: {case['text']} -> 期待:{case['expected']}, 実際:右:{nct_result.right_eye}, 左:{nct_result.left_eye}")
        
        results['accuracy'] = results['success'] / results['total'] * 100
        return results
    
    def test_refraction_extraction(self) -> Dict[str, float]:
        """レフ値抽出テスト"""
        results = {'total': 0, 'success': 0, 'accuracy': 0.0}
        
        for case in self.test_cases['refraction']:
            results['total'] += 1
            
            # テキスト結果を模擬
            text_results = [{'text': case['text'], 'confidence': 0.9, 'bbox': [], 'source': 'test'}]
            
            # レフ値抽出実行
            ref_result = self.ocr.extract_refraction_values(text_results)
            
            # 結果検証（誤差±0.25D以内）
            if (ref_result.sphere is not None and 
                abs(ref_result.sphere - case['expected']['sphere']) <= 0.25 and
                ref_result.cylinder is not None and
                abs(ref_result.cylinder - case['expected']['cylinder']) <= 0.25 and
                ref_result.axis == case['expected']['axis'] and
                ref_result.qa_flag == "OK"):
                results['success'] += 1
                logger.info(f"レフ値テスト成功: {case['text']} -> S:{ref_result.sphere}, C:{ref_result.cylinder}, Ax:{ref_result.axis}")
            else:
                logger.error(f"レフ値テスト失敗: {case['text']} -> 期待:{case['expected']}, 実際:S:{ref_result.sphere}, C:{ref_result.cylinder}, Ax:{ref_result.axis}")
        
        results['accuracy'] = results['success'] / results['total'] * 100
        return results
    
    def test_iol_extraction(self) -> Dict[str, float]:
        """IOLシール抽出テスト"""
        results = {'total': 0, 'success': 0, 'accuracy': 0.0}
        
        for case in self.test_cases['iol']:
            results['total'] += 1
            
            # テキスト結果を模擬
            text_results = [{'text': case['text'], 'confidence': 0.9, 'bbox': [], 'source': 'test'}]
            
            # IOL抽出実行
            iol_result = self.ocr.extract_iol_seal_info(text_results)
            
            # 結果検証
            if (iol_result.power == case['expected']['power'] and
                iol_result.product_name == case['expected']['product'] and
                iol_result.qa_flag == "OK"):
                results['success'] += 1
                logger.info(f"IOLテスト成功: {case['text']} -> 度数:{iol_result.power}, 製品:{iol_result.product_name}")
            else:
                logger.error(f"IOLテスト失敗: {case['text']} -> 期待:{case['expected']}, 実際:度数:{iol_result.power}, 製品:{iol_result.product_name}")
        
        results['accuracy'] = results['success'] / results['total'] * 100
        return results
    
    def test_edge_cases(self) -> Dict[str, int]:
        """エッジケーステスト"""
        edge_cases = [
            {'text': 'NCT: 5.0 / 50.0', 'expected': 'valid'},  # 境界値
            {'text': 'NCT: 4.9 / 50.1', 'expected': 'invalid'},  # 範囲外
            {'text': 'S: -20.1 C: -6.1 Ax: 181', 'expected': 'invalid'},  # 範囲外
            {'text': 'IOL: +30.1D', 'expected': 'invalid'},  # 範囲外
            {'text': 'NCT: abc / def', 'expected': 'invalid'},  # 無効な文字
        ]
        
        results = {'total': len(edge_cases), 'passed': 0}
        
        for case in edge_cases:
            text_results = [{'text': case['text'], 'confidence': 0.9, 'bbox': [], 'source': 'test'}]
            
            # 各項目でテスト
            nct_result = self.ocr.extract_nct_values(text_results)
            ref_result = self.ocr.extract_refraction_values(text_results)
            iol_result = self.ocr.extract_iol_seal_info(text_results)
            
            # エッジケースの検証
            if case['expected'] == 'invalid':
                if (nct_result.qa_flag == "NOT_FOUND" or 
                    ref_result.qa_flag == "NOT_FOUND" or 
                    iol_result.qa_flag == "NOT_FOUND"):
                    results['passed'] += 1
                    logger.info(f"エッジケース成功: {case['text']} -> 適切に無効として判定")
                else:
                    logger.error(f"エッジケース失敗: {case['text']} -> 無効な値が有効として判定された")
            else:
                if (nct_result.qa_flag == "OK" or 
                    ref_result.qa_flag == "OK" or 
                    iol_result.qa_flag == "OK"):
                    results['passed'] += 1
                    logger.info(f"エッジケース成功: {case['text']} -> 適切に有効として判定")
                else:
                    logger.error(f"エッジケース失敗: {case['text']} -> 有効な値が無効として判定された")
        
        return results
    
    def run_all_tests(self) -> Dict[str, Any]:
        """全テスト実行"""
        logger.info("=== P2 OCR テスト開始 ===")
        
        results = {}
        
        # NCTテスト
        logger.info("\n--- NCT抽出テスト ---")
        nct_results = self.test_nct_extraction()
        results['nct'] = nct_results
        logger.info(f"NCT精度: {nct_results['accuracy']:.1f}% ({nct_results['success']}/{nct_results['total']})")
        
        # レフ値テスト
        logger.info("\n--- レフ値抽出テスト ---")
        ref_results = self.test_refraction_extraction()
        results['refraction'] = ref_results
        logger.info(f"レフ値精度: {ref_results['accuracy']:.1f}% ({ref_results['success']}/{ref_results['total']})")
        
        # IOLテスト
        logger.info("\n--- IOLシール抽出テスト ---")
        iol_results = self.test_iol_extraction()
        results['iol'] = iol_results
        logger.info(f"IOL精度: {iol_results['accuracy']:.1f}% ({iol_results['success']}/{iol_results['total']})")
        
        # エッジケーステスト
        logger.info("\n--- エッジケーステスト ---")
        edge_results = self.test_edge_cases()
        results['edge_cases'] = edge_results
        logger.info(f"エッジケース通過率: {edge_results['passed']}/{edge_results['total']}")
        
        # 合格基準チェック
        logger.info("\n--- 合格基準チェック ---")
        passed_criteria = []
        
        if nct_results['accuracy'] >= 98.0:
            passed_criteria.append("NCT ≥98%")
            logger.info("✅ NCT精度基準達成")
        else:
            logger.error(f"❌ NCT精度基準未達成: {nct_results['accuracy']:.1f}% < 98%")
        
        if ref_results['accuracy'] >= 95.0:  # レフ値は誤差±0.25D以内
            passed_criteria.append("レフ値誤差≤±0.25D")
            logger.info("✅ レフ値精度基準達成")
        else:
            logger.error(f"❌ レフ値精度基準未達成: {ref_results['accuracy']:.1f}% < 95%")
        
        if iol_results['accuracy'] >= 95.0:
            passed_criteria.append("IOLシール正確読取")
            logger.info("✅ IOLシール精度基準達成")
        else:
            logger.error(f"❌ IOLシール精度基準未達成: {iol_results['accuracy']:.1f}% < 95%")
        
        results['passed_criteria'] = passed_criteria
        results['all_passed'] = len(passed_criteria) == 3
        
        logger.info(f"\n=== テスト結果サマリー ===")
        logger.info(f"合格基準達成: {len(passed_criteria)}/3")
        logger.info(f"全体結果: {'✅ 合格' if results['all_passed'] else '❌ 不合格'}")
        
        return results

def main():
    """メイン実行"""
    test_suite = P2OCRTestSuite()
    results = test_suite.run_all_tests()
    
    # 結果をJSONファイルに保存
    output_file = Path(__file__).parent / 'p2_test_results.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"テスト結果を保存: {output_file}")
    
    # 終了コード
    sys.exit(0 if results['all_passed'] else 1)

if __name__ == '__main__':
    main()
