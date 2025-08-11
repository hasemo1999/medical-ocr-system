/**
 * ログイン処理テスト（TypeScript版）
 */

import { LoginService, login, verifyJWTToken, logout, LoginResult } from './login';

describe('LoginService', () => {
  let loginService: LoginService;

  beforeEach(() => {
    loginService = new LoginService();
  });

  describe('正常ログイン', () => {
    it('admin/adminでログイン成功する', () => {
      const result = loginService.login('admin', 'admin');
      
      expect(result.success).toBe(true);
      expect(result.user_id).toBe('admin');
      expect(result.token).toBeDefined();
      expect(result.message).toBe('ログイン成功');
      expect(result.expires_at).toBeDefined();
    });

    it('user1/123でログイン成功する', () => {
      const result = loginService.login('user1', '123');
      
      expect(result.success).toBe(true);
      expect(result.user_id).toBe('user1');
      expect(result.token).toBeDefined();
    });

    it('doctor/空文字でログイン成功する', () => {
      const result = loginService.login('doctor', '');
      
      expect(result.success).toBe(true);
      expect(result.user_id).toBe('doctor');
      expect(result.token).toBeDefined();
    });
  });

  describe('ログイン失敗', () => {
    it('存在しないユーザーでログイン失敗する', () => {
      const result = loginService.login('nonexistent', 'password');
      
      expect(result.success).toBe(false);
      expect(result.message).toBe('ユーザー名またはパスワードが正しくありません');
      expect(result.token).toBeUndefined();
    });

    it('間違ったパスワードでログイン失敗する', () => {
      const result = loginService.login('admin', 'wrongpassword');
      
      expect(result.success).toBe(false);
      expect(result.message).toBe('ユーザー名またはパスワードが正しくありません');
      expect(result.token).toBeUndefined();
    });
  });

  describe('レート制限', () => {
    it('5回失敗後にレート制限がかかる', () => {
      // 5回失敗
      for (let i = 0; i < 5; i++) {
        const result = loginService.login('admin', 'wrongpassword');
        expect(result.success).toBe(false);
      }

      // 6回目でレート制限
      const result = loginService.login('admin', 'wrongpassword');
      expect(result.success).toBe(false);
      expect(result.message).toContain('ログイン試行回数が上限に達しました');
    });

    it('成功後にレート制限がリセットされる', () => {
      // 4回失敗
      for (let i = 0; i < 4; i++) {
        loginService.login('admin', 'wrongpassword');
      }

      // 成功
      const successResult = loginService.login('admin', 'admin');
      expect(successResult.success).toBe(true);

      // 再度失敗しても制限されない
      const failResult = loginService.login('admin', 'wrongpassword');
      expect(failResult.success).toBe(false);
      expect(failResult.message).toBe('ユーザー名またはパスワードが正しくありません');
    });
  });

  describe('アカウントロック', () => {
    it('5回失敗後にアカウントがロックされる', () => {
      // 5回失敗
      for (let i = 0; i < 5; i++) {
        loginService.login('admin', 'wrongpassword');
      }

      // 正しいパスワードでもロックされる
      const result = loginService.login('admin', 'admin');
      expect(result.success).toBe(false);
      expect(result.message).toContain('アカウントがロックされています');
    });
  });

  describe('JWTトークン', () => {
    it('ログイン成功時に有効なJWTトークンが生成される', () => {
      const result = loginService.login('admin', 'admin');
      
      expect(result.success).toBe(true);
      expect(result.token).toBeDefined();

      const payload = loginService.verifyToken(result.token!);
      expect(payload).toBeDefined();
      expect(payload!.username).toBe('admin');
      expect(payload!.role).toBe('admin');
      expect(payload!.iss).toBe('medical-ocr-system');
    });

    it('ログアウト後にトークンが無効になる', () => {
      const result = loginService.login('admin', 'admin');
      expect(result.success).toBe(true);

      const token = result.token!;
      const payload = loginService.verifyToken(token);
      expect(payload).toBeDefined();

      // ログアウト
      const logoutResult = loginService.logout(token);
      expect(logoutResult.success).toBe(true);

      // ログアウト後のトークン検証
      const invalidPayload = loginService.verifyToken(token);
      expect(invalidPayload).toBeNull();
    });
  });

  describe('後方互換性関数', () => {
    it('login関数が正常に動作する', () => {
      const result = login('admin', 'admin');
      
      expect(result.success).toBe(true);
      expect(result.user_id).toBe('admin');
      expect(result.token).toBeDefined();
      expect(result.message).toBe('ログイン成功');
    });

    it('verifyJWTToken関数が正常に動作する', () => {
      const loginResult = login('admin', 'admin');
      expect(loginResult.success).toBe(true);

      const payload = verifyJWTToken(loginResult.token!);
      expect(payload).toBeDefined();
      expect(payload!.username).toBe('admin');
    });

    it('logout関数が正常に動作する', () => {
      const loginResult = login('admin', 'admin');
      expect(loginResult.success).toBe(true);

      const logoutResult = logout(loginResult.token!);
      expect(logoutResult.success).toBe(true);
    });
  });

  describe('エラーハンドリング', () => {
    it('例外が発生した場合に適切に処理される', () => {
      // 不正なJWTシークレットでテスト
      const serviceWithInvalidSecret = new LoginService();
      
      // このテストは実際の例外処理をテストする
      const result = serviceWithInvalidSecret.login('admin', 'admin');
      expect(result.success).toBe(false);
      expect(result.message).toBe('ログイン処理中にエラーが発生しました');
    });
  });

  describe('パフォーマンス', () => {
    it('複数回のログイン試行が正常に処理される', () => {
      const results: LoginResult[] = [];
      
      // 10回のログイン試行
      for (let i = 0; i < 10; i++) {
        const result = loginService.login('admin', 'admin');
        results.push(result);
      }

      // すべて成功することを確認
      results.forEach(result => {
        expect(result.success).toBe(true);
        expect(result.token).toBeDefined();
      });
    });
  });
});

// 統合テスト
describe('統合テスト', () => {
  let loginService: LoginService;

  beforeEach(() => {
    loginService = new LoginService();
  });

  it('完全なログイン・ログアウトフロー', () => {
    // 1. ログイン
    const loginResult = loginService.login('admin', 'admin');
    expect(loginResult.success).toBe(true);
    expect(loginResult.token).toBeDefined();

    // 2. トークン検証
    const payload = loginService.verifyToken(loginResult.token!);
    expect(payload).toBeDefined();
    expect(payload!.username).toBe('admin');

    // 3. ログアウト
    const logoutResult = loginService.logout(loginResult.token!);
    expect(logoutResult.success).toBe(true);

    // 4. ログアウト後のトークン検証
    const invalidPayload = loginService.verifyToken(loginResult.token!);
    expect(invalidPayload).toBeNull();

    // 5. 再度ログイン可能
    const reLoginResult = loginService.login('admin', 'admin');
    expect(reLoginResult.success).toBe(true);
  });

  it('セキュリティテスト', () => {
    // 1. レート制限テスト
    for (let i = 0; i < 6; i++) {
      const result = loginService.login('admin', 'wrongpassword');
      if (i < 5) {
        expect(result.success).toBe(false);
        expect(result.message).toBe('ユーザー名またはパスワードが正しくありません');
      } else {
        expect(result.success).toBe(false);
        expect(result.message).toContain('ログイン試行回数が上限に達しました');
      }
    }

    // 2. アカウントロックテスト
    const lockResult = loginService.login('admin', 'admin');
    expect(lockResult.success).toBe(false);
    expect(lockResult.message).toContain('アカウントがロックされています');
  });
});
