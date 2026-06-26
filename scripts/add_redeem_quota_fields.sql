ALTER TABLE mc_user_accounts
    ADD COLUMN redeem_balance INT NOT NULL DEFAULT 0 COMMENT 'redeem code token balance' AFTER free_last_grant_at,
    ADD COLUMN redeem_total_amount BIGINT NOT NULL DEFAULT 0 COMMENT 'active redeem code token total' AFTER redeem_balance;

ALTER TABLE mc_token_usage_logs
    ADD COLUMN redeem_amount INT NOT NULL DEFAULT 0 COMMENT 'redeem code token consumed' AFTER bonus_amount;

ALTER TABLE mc_redeem_code
    ADD COLUMN remaining_amount INT NOT NULL DEFAULT 0 COMMENT 'remaining token amount after redeem' AFTER valid_days,
    ADD COLUMN token_expired_time DATETIME NULL COMMENT 'token expire time after redeem' AFTER code_expired_time;

CREATE INDEX idx_redeem_token_expire ON mc_redeem_code (status, token_expired_time);
