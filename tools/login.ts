/**
 * ログイン処理モジュール（TypeScript版）
 * - ユーザー認証
 * - JWTトークン生成
 * - セッション管理
 */

import jwt from 'jsonwebtoken';
import crypto from 'crypto';

// 型定義
export interface LoginResult {
  success: boolean;
  token?: string;
  user_id?: string;
  message: string;
  expires_at?: Date;
}

export interface User {
  username: string;
  password_hash: string;
  role: string;
  is_active: boolean;
  failed_attempts: number;
  locked_until?: Date;
}

export interface JWTPayload {
  username: string;
  role: string;
  exp: number;
  iat: number;
  iss: string;
  jti: string;
}

// 設定
const JWT_SECRET = process.env['JWT_SECRET'] || 'your-secret-key';
const JWT_ALGORITHM = 'HS256';
const TOKEN_EXPIRES_HOURS = 24;
const MAX_FAILED_ATTEMPTS = 5;
const LOCK_DURATION_MINUTES = 15;
const RATE_LIMIT_MAX_ATTEMPTS = 5;
const RATE_LIMIT_WINDOW_MINUTES = 15;

// ユーザー管理クラス
class UserManager {
  private users: Map<string, User> = new Map();

  constructor() {
    this.loadSampleUsers();
  }

  private loadSampleUsers(): void {
    const sampleData: Record<string, [string, string]> = {
      'admin': ['8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', 'admin'],
      'user1': ['a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3', 'user'],
      'doctor': ['e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'doctor']
    };

    for (const [username, [passwordHash, role]] of Object.entries(sampleData)) {
      this.users.set(username, {
        username,
        password_hash: passwordHash,
        role,
        is_active: true,
        failed_attempts: 0
      });
    }
  }

  getUser(username: string): User | undefined {
    return this.users.get(username);
  }

  updateFailedAttempts(username: string): void {
    const user = this.users.get(username);
    if (user) {
      user.failed_attempts += 1;
      
      // 5回失敗で15分ロック
      if (user.failed_attempts >= MAX_FAILED_ATTEMPTS) {
        user.locked_until = new Date(Date.now() + LOCK_DURATION_MINUTES * 60 * 1000);
      }
    }
  }

  resetFailedAttempts(username: string): void {
    const user = this.users.get(username);
    if (user) {
      user.failed_attempts = 0;
      user.locked_until = undefined as Date | undefined;
    }
  }
}

// レート制限クラス
class RateLimiter {
  private attempts: Map<string, number[]> = new Map();
  private readonly maxAttempts: number;
  private readonly windowMinutes: number;

  constructor(maxAttempts: number = RATE_LIMIT_MAX_ATTEMPTS, windowMinutes: number = RATE_LIMIT_WINDOW_MINUTES) {
    this.maxAttempts = maxAttempts;
    this.windowMinutes = windowMinutes;
  }

  isAllowed(username: string): boolean {
    const now = Date.now();
    const windowStart = now - (this.windowMinutes * 60 * 1000);
    
    const userAttempts = this.attempts.get(username) || [];
    
    // 古い試行を削除
    const recentAttempts = userAttempts.filter(attemptTime => attemptTime > windowStart);
    
    // 制限チェック
    if (recentAttempts.length >= this.maxAttempts) {
      return false;
    }
    
    recentAttempts.push(now);
    this.attempts.set(username, recentAttempts);
    return true;
  }

  resetAttempts(username: string): void {
    this.attempts.delete(username);
  }
}

// JWT管理クラス
class JWTManager {
  private readonly secretKey: string;
  private readonly algorithm: string;
  private tokenBlacklist: Set<string> = new Set();

  constructor(secretKey?: string) {
    this.secretKey = secretKey || JWT_SECRET;
    this.algorithm = JWT_ALGORITHM;
  }

  generateToken(username: string, role: string, expiresHours: number = TOKEN_EXPIRES_HOURS): string {
    const payload: JWTPayload = {
      username,
      role,
      exp: Math.floor(Date.now() / 1000) + (expiresHours * 60 * 60),
      iat: Math.floor(Date.now() / 1000),
      iss: 'medical-ocr-system',
      jti: crypto.randomBytes(16).toString('hex')
    };

    return jwt.sign(payload, this.secretKey, { algorithm: this.algorithm as jwt.Algorithm });
  }

  verifyToken(token: string): JWTPayload | null {
    try {
      // ブラックリストチェック
      if (this.tokenBlacklist.has(token)) {
        return null;
      }

      const payload = jwt.verify(token, this.secretKey, { algorithms: [this.algorithm as jwt.Algorithm] }) as JWTPayload;
      return payload;
    } catch (error) {
      if (error instanceof jwt.TokenExpiredError) {
        console.warn('JWTトークンの有効期限が切れています');
      } else if (error instanceof jwt.JsonWebTokenError) {
        console.warn('無効なJWTトークンです');
      }
      return null;
    }
  }

  blacklistToken(token: string): void {
    this.tokenBlacklist.add(token);
  }
}

// ログインサービスクラス
export class LoginService {
  private userManager: UserManager;
  private jwtManager: JWTManager;
  private rateLimiter: RateLimiter;

  constructor() {
    this.userManager = new UserManager();
    this.jwtManager = new JWTManager();
    this.rateLimiter = new RateLimiter();
  }

  login(username: string, password: string): LoginResult {
    try {
      // レート制限チェック
      if (!this.rateLimiter.isAllowed(username)) {
        return {
          success: false,
          message: 'ログイン試行回数が上限に達しました。しばらく時間をおいてから再試行してください。'
        };
      }

      // ユーザー存在チェック
      const user = this.userManager.getUser(username);
      if (!user) {
        return {
          success: false,
          message: 'ユーザー名またはパスワードが正しくありません'
        };
      }

      // アカウントロックチェック
      if (user.locked_until && user.locked_until > new Date()) {
        const remainingTime = user.locked_until.getTime() - Date.now();
        const minutes = Math.ceil(remainingTime / (60 * 1000));
        return {
          success: false,
          message: `アカウントがロックされています。${minutes}分後に再試行してください。`
        };
      }

      // パスワード検証
      const passwordHash = this.hashPassword(password);
      if (user.password_hash !== passwordHash) {
        this.userManager.updateFailedAttempts(username);
        return {
          success: false,
          message: 'ユーザー名またはパスワードが正しくありません'
        };
      }

      // ログイン成功
      this.userManager.resetFailedAttempts(username);
      this.rateLimiter.resetAttempts(username);

      // JWTトークン生成
      const token = this.jwtManager.generateToken(username, user.role);
      const expiresAt = new Date(Date.now() + TOKEN_EXPIRES_HOURS * 60 * 60 * 1000);

      console.log(`ログイン成功: ${username}`);

      return {
        success: true,
        token,
        user_id: username,
        message: 'ログイン成功',
        expires_at: expiresAt
      };

    } catch (error) {
      console.error('ログイン処理エラー:', error);
      return {
        success: false,
        message: 'ログイン処理中にエラーが発生しました'
      };
    }
  }

  logout(token: string): { success: boolean } {
    try {
      this.jwtManager.blacklistToken(token);
      return { success: true };
    } catch (error) {
      console.error('ログアウト処理エラー:', error);
      return { success: false };
    }
  }

  verifyToken(token: string): JWTPayload | null {
    return this.jwtManager.verifyToken(token);
  }

  private hashPassword(password: string): string {
    return crypto.createHash('sha256').update(password).digest('hex');
  }
}

// グローバルインスタンス
export const loginService = new LoginService();

// 後方互換性のための関数
export function login(username: string, password: string): { success: boolean; token?: string; user_id?: string; message: string } {
  const result = loginService.login(username, password);
  
  if (result.success) {
    return {
      success: true,
      token: result.token || undefined,
      user_id: result.user_id || undefined,
      message: result.message
    };
  } else {
    return {
      success: false,
      message: result.message
    };
  }
}

export function verifyJWTToken(token: string): JWTPayload | null {
  return loginService.verifyToken(token);
}

export function logout(token: string): { success: boolean } {
  return loginService.logout(token);
}

// テスト実行
if (require.main === module) {
  console.log('=== TypeScript版ログインテスト ===');
  
  // 正常ログイン
  const result = loginService.login('admin', 'admin');
  console.log('admin/admin:', result);
  
  // 失敗ログイン（レート制限テスト）
  for (let i = 0; i < 6; i++) {
    const failResult = loginService.login('admin', 'wrong_password');
    console.log(`試行${i + 1}:`, failResult.message);
  }
  
  // トークン検証
  if (result.success && result.token) {
    const payload = loginService.verifyToken(result.token);
    console.log('トークン検証:', payload);
    
    // ログアウト
    const logoutResult = loginService.logout(result.token);
    console.log('ログアウト:', logoutResult);
    
    // ログアウト後のトークン検証
    const invalidPayload = loginService.verifyToken(result.token);
    console.log('ログアウト後トークン検証:', invalidPayload);
  }
}
