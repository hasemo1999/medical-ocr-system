# -*- coding: utf-8 -*-
"""
ログイン処理モジュール（最適化版）
- ユーザー認証
- JWTトークン生成
- セッション管理
- レート制限
- セキュリティ強化
"""

import jwt
import hashlib
import datetime
import time
import secrets
from typing import Dict, Optional, Union, Tuple
from dataclasses import dataclass
from functools import lru_cache
import logging
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)

@dataclass
class LoginResult:
    """ログイン結果データクラス"""
    success: bool
    token: Optional[str] = None
    user_id: Optional[str] = None
    message: str = ""
    expires_at: Optional[datetime.datetime] = None

@dataclass
class User:
    """ユーザー情報データクラス"""
    username: str
    password_hash: str
    role: str
    is_active: bool = True
    failed_attempts: int = 0
    locked_until: Optional[datetime.datetime] = None

class RateLimiter:
    """レート制限クラス"""
    
    def __init__(self, max_attempts: int = 5, window_minutes: int = 15):
        self.max_attempts = max_attempts
        self.window_minutes = window_minutes
        self.attempts = defaultdict(list)
        self.lock = threading.Lock()
    
    def is_allowed(self, username: str) -> bool:
        """レート制限チェック"""
        with self.lock:
            now = time.time()
            window_start = now - (self.window_minutes * 60)
            
            # 古い試行を削除
            self.attempts[username] = [
                attempt_time for attempt_time in self.attempts[username]
                if attempt_time > window_start
            ]
            
            # 制限チェック
            if len(self.attempts[username]) >= self.max_attempts:
                return False
            
            self.attempts[username].append(now)
            return True
    
    def reset_attempts(self, username: str):
        """試行回数をリセット"""
        with self.lock:
            self.attempts[username].clear()

class UserManager:
    """ユーザー管理クラス"""
    
    def __init__(self):
        self.users: Dict[str, User] = {}
        self._load_sample_users()
    
    def _load_sample_users(self):
        """サンプルユーザー読み込み"""
        sample_data = {
            'admin': ('8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', 'admin'),
            'user1': ('a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3', 'user'),
            'doctor': ('e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'doctor')
        }
        
        for username, (password_hash, role) in sample_data.items():
            self.users[username] = User(username=username, password_hash=password_hash, role=role)
    
    def get_user(self, username: str) -> Optional[User]:
        """ユーザー取得"""
        return self.users.get(username)
    
    def update_failed_attempts(self, username: str):
        """失敗試行回数更新"""
        if username in self.users:
            user = self.users[username]
            user.failed_attempts += 1
            
            # 5回失敗で15分ロック
            if user.failed_attempts >= 5:
                user.locked_until = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    
    def reset_failed_attempts(self, username: str):
        """失敗試行回数リセット"""
        if username in self.users:
            user = self.users[username]
            user.failed_attempts = 0
            user.locked_until = None

class JWTManager:
    """JWT管理クラス"""
    
    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or secrets.token_urlsafe(32)
        self.algorithm = 'HS256'
        self.token_blacklist = set()
        self.lock = threading.Lock()
    
    def generate_token(self, username: str, role: str, expires_hours: int = 24) -> str:
        """JWTトークン生成"""
        payload = {
            'username': username,
            'role': role,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=expires_hours),
            'iat': datetime.datetime.utcnow(),
            'iss': 'medical-ocr-system',
            'jti': secrets.token_urlsafe(16)  # JWT ID
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """JWTトークン検証"""
        try:
            # ブラックリストチェック
            with self.lock:
                if token in self.token_blacklist:
                    return None
            
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("JWTトークンの有効期限が切れています")
            return None
        except jwt.InvalidTokenError:
            logger.warning("無効なJWTトークンです")
            return None
    
    def blacklist_token(self, token: str):
        """トークンをブラックリストに追加"""
        with self.lock:
            self.token_blacklist.add(token)

class LoginService:
    """ログインサービスクラス"""
    
    def __init__(self):
        self.user_manager = UserManager()
        self.jwt_manager = JWTManager()
        self.rate_limiter = RateLimiter()
    
    def login(self, username: str, password: str) -> LoginResult:
        """ユーザーログイン処理（最適化版）"""
        try:
            # レート制限チェック
            if not self.rate_limiter.is_allowed(username):
                return LoginResult(
                    success=False,
                    message="ログイン試行回数が上限に達しました。しばらく時間をおいてから再試行してください。"
                )
            
            # ユーザー存在チェック
            user = self.user_manager.get_user(username)
            if not user:
                return LoginResult(
                    success=False,
                    message="ユーザー名またはパスワードが正しくありません"
                )
            
            # アカウントロックチェック
            if user.locked_until and user.locked_until > datetime.datetime.utcnow():
                remaining_time = user.locked_until - datetime.datetime.utcnow()
                minutes = int(remaining_time.total_seconds() / 60)
                return LoginResult(
                    success=False,
                    message=f"アカウントがロックされています。{minutes}分後に再試行してください。"
                )
            
            # パスワード検証
            password_hash = self._hash_password(password)
            if user.password_hash != password_hash:
                self.user_manager.update_failed_attempts(username)
                return LoginResult(
                    success=False,
                    message="ユーザー名またはパスワードが正しくありません"
                )
            
            # ログイン成功
            self.user_manager.reset_failed_attempts(username)
            self.rate_limiter.reset_attempts(username)
            
            # JWTトークン生成
            token = self.jwt_manager.generate_token(username, user.role)
            expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
            
            logger.info(f"ログイン成功: {username}")
            
            return LoginResult(
                success=True,
                token=token,
                user_id=username,
                message="ログイン成功",
                expires_at=expires_at
            )
            
        except Exception as e:
            logger.error(f"ログイン処理エラー: {e}")
            return LoginResult(
                success=False,
                message="ログイン処理中にエラーが発生しました"
            )
    
    def logout(self, token: str) -> Dict[str, bool]:
        """ログアウト処理"""
        try:
            self.jwt_manager.blacklist_token(token)
            return {'success': True}
        except Exception as e:
            logger.error(f"ログアウト処理エラー: {e}")
            return {'success': False}
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """トークン検証"""
        return self.jwt_manager.verify_token(token)
    
    @staticmethod
    @lru_cache(maxsize=1000)
    def _hash_password(password: str) -> str:
        """パスワードハッシュ化（キャッシュ付き）"""
        return hashlib.sha256(password.encode()).hexdigest()

# グローバルインスタンス
login_service = LoginService()

# 後方互換性のための関数
def login(username: str, password: str) -> Dict[str, Union[str, bool]]:
    """後方互換性のためのログイン関数"""
    result = login_service.login(username, password)
    
    if result.success:
        return {
            'success': True,
            'token': result.token,
            'user_id': result.user_id,
            'message': result.message
        }
    else:
        return {
            'success': False,
            'message': result.message
        }

def verify_jwt_token(token: str) -> Optional[Dict]:
    """後方互換性のためのトークン検証関数"""
    return login_service.verify_token(token)

def logout(token: str) -> Dict[str, bool]:
    """後方互換性のためのログアウト関数"""
    return login_service.logout(token)

if __name__ == '__main__':
    # テスト実行
    print("=== 最適化版ログインテスト ===")
    
    # 正常ログイン
    result = login_service.login('admin', 'admin')
    print(f"admin/admin: {result}")
    
    # 失敗ログイン（レート制限テスト）
    for i in range(6):
        result = login_service.login('admin', 'wrong_password')
        print(f"試行{i+1}: {result.message}")
    
    # トークン検証
    if result.success:
        token = result.token
        payload = login_service.verify_token(token)
        print(f"トークン検証: {payload}")
    
    # ログアウト
    if result.success:
        logout_result = login_service.logout(token)
        print(f"ログアウト: {logout_result}")
        
        # ログアウト後のトークン検証
        payload = login_service.verify_token(token)
        print(f"ログアウト後トークン検証: {payload}")
