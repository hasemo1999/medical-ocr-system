# -*- coding: utf-8 -*-
"""
ログイン処理モジュール
- ユーザー認証
- JWTトークン生成
- セッション管理
"""

import jwt
import hashlib
import datetime
from typing import Dict, Optional, Union
import logging

logger = logging.getLogger(__name__)

def login(username: str, password: str) -> Dict[str, Union[str, bool]]:
    """ユーザーログイン処理
    
    Args:
        username (str): ユーザー名
        password (str): パスワード
        
    Returns:
        Dict[str, Union[str, bool]]: ログイン結果
            - success (bool): ログイン成功フラグ
            - token (str): JWTトークン（成功時）
            - message (str): エラーメッセージ（失敗時）
            - user_id (str): ユーザーID（成功時）
    """
    try:
        # パスワードハッシュ化
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # ユーザー認証（実際の実装ではDBから検索）
        if authenticate_user(username, password_hash):
            # JWTトークン生成
            token = generate_jwt_token(username)
            
            return {
                'success': True,
                'token': token,
                'user_id': username,
                'message': 'ログイン成功'
            }
        else:
            return {
                'success': False,
                'message': 'ユーザー名またはパスワードが正しくありません'
            }
            
    except Exception as e:
        logger.error(f"ログイン処理エラー: {e}")
        return {
            'success': False,
            'message': 'ログイン処理中にエラーが発生しました'
        }

def authenticate_user(username: str, password_hash: str) -> bool:
    """ユーザー認証
    
    Args:
        username (str): ユーザー名
        password_hash (str): ハッシュ化されたパスワード
        
    Returns:
        bool: 認証成功フラグ
    """
    # 実際の実装ではデータベースからユーザー情報を取得
    # ここではサンプルユーザーで認証
    sample_users = {
        'admin': '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918',  # admin
        'user1': 'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3',  # 123
        'doctor': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'   # 空文字
    }
    
    return username in sample_users and sample_users[username] == password_hash

def generate_jwt_token(username: str, secret_key: str = "your-secret-key") -> str:
    """JWTトークン生成
    
    Args:
        username (str): ユーザー名
        secret_key (str): 秘密鍵
        
    Returns:
        str: JWTトークン
    """
    payload = {
        'username': username,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24),  # 24時間有効
        'iat': datetime.datetime.utcnow(),
        'iss': 'medical-ocr-system'
    }
    
    token = jwt.encode(payload, secret_key, algorithm='HS256')
    return token

def verify_jwt_token(token: str, secret_key: str = "your-secret-key") -> Optional[Dict]:
    """JWTトークン検証
    
    Args:
        token (str): JWTトークン
        secret_key (str): 秘密鍵
        
    Returns:
        Optional[Dict]: トークンペイロード（有効な場合）、None（無効な場合）
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWTトークンの有効期限が切れています")
        return None
    except jwt.InvalidTokenError:
        logger.warning("無効なJWTトークンです")
        return None

def logout(token: str) -> Dict[str, bool]:
    """ログアウト処理
    
    Args:
        token (str): JWTトークン
        
    Returns:
        Dict[str, bool]: ログアウト結果
    """
    # 実際の実装ではトークンブラックリストに追加
    # ここでは単純に成功を返す
    return {'success': True}

if __name__ == '__main__':
    # テスト実行
    print("=== ログインテスト ===")
    
    # 正常ログイン
    result = login('admin', 'admin')
    print(f"admin/admin: {result}")
    
    # 失敗ログイン
    result = login('admin', 'wrong_password')
    print(f"admin/wrong: {result}")
    
    # トークン検証
    if result['success']:
        token = result['token']
        payload = verify_jwt_token(token)
        print(f"トークン検証: {payload}")
