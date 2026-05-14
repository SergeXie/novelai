ALTER TABLE `mc_user_accounts`
  ADD COLUMN `monthly_total_amount` BIGINT NOT NULL DEFAULT 0 COMMENT '当前会员周期付费月度额度总额' AFTER `monthly_balance`,
  ADD COLUMN `permanent_total_amount` BIGINT NOT NULL DEFAULT 0 COMMENT '永久购买额度累计总额' AFTER `permanent_balance`;

-- 历史数据没有完整消耗拆分时，只能先用当前余额兜底初始化。
UPDATE `mc_user_accounts`
SET `monthly_total_amount` = GREATEST(`monthly_balance`, 0)
WHERE `monthly_total_amount` = 0 AND `monthly_balance` > 0;

UPDATE `mc_user_accounts`
SET `permanent_total_amount` = GREATEST(`permanent_balance`, 0)
WHERE `permanent_total_amount` = 0 AND `permanent_balance` > 0;
