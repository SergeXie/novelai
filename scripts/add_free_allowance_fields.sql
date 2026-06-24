ALTER TABLE mc_user_accounts
    ADD COLUMN free_balance INT NOT NULL DEFAULT 0 COMMENT '本月免费额度余额' AFTER bonus_balance,
    ADD COLUMN free_total_amount BIGINT NOT NULL DEFAULT 0 COMMENT '本月免费额度发放总量' AFTER free_balance,
    ADD COLUMN free_last_grant_at DATETIME NULL COMMENT '最近一次免费额度发放时间' AFTER free_total_amount;

ALTER TABLE mc_token_usage_logs
    ADD COLUMN free_amount INT NOT NULL DEFAULT 0 COMMENT '免费额度变动' AFTER monthly_amount;
