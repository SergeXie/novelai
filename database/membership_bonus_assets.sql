ALTER TABLE `mc_user_accounts`
  ADD COLUMN `bonus_balance` INT NOT NULL DEFAULT 0 COMMENT '补给奖励Token余额（会员周五赠送，每月清零）' AFTER `permanent_balance`,
  ADD COLUMN `bonus_total_amount` BIGINT NOT NULL DEFAULT 0 COMMENT '当前周期补给奖励总额度' AFTER `total_amount`;

ALTER TABLE `ai_novel_generate_log`
  ADD COLUMN `bonusDeduct` INT NOT NULL DEFAULT 0 COMMENT '本次消耗的补给奖励额度' AFTER `monthlyDeduct`;

ALTER TABLE `mc_token_usage_logs`
  ADD COLUMN `bonus_amount` INT NOT NULL DEFAULT 0 COMMENT '补给奖励额度变动' AFTER `monthly_amount`;

CREATE TABLE IF NOT EXISTS `mc_membership_token_grant_plans` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '计划ID',
  `user_id` BIGINT NOT NULL COMMENT '用户ID',
  `order_no` VARCHAR(64) NOT NULL COMMENT '订单号',
  `level_code` VARCHAR(32) NOT NULL COMMENT '会员等级',
  `cycle_no` INT NOT NULL COMMENT '第几个月周期，从1开始',
  `period_no` INT NOT NULL COMMENT '周期内期数，-1=清零，0=基础额度，1-4=周五补给',
  `plan_type` VARCHAR(16) NOT NULL DEFAULT 'BASE' COMMENT '计划类型 BASE/BONUS/RESET',
  `amount` INT NOT NULL DEFAULT 0 COMMENT '本期发放Token数量',
  `scheduled_at` DATETIME NOT NULL COMMENT '计划执行时间',
  `issued_at` DATETIME NULL COMMENT '实际执行时间',
  `membership_expire_at` DATETIME NOT NULL COMMENT '本订单会员到期时间',
  `status` VARCHAR(16) NOT NULL DEFAULT 'PENDING' COMMENT 'PENDING/ISSUED/CANCELED/FAILED',
  `extra` JSON NULL COMMENT '扩展信息',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_membership_token_grant_period` (`order_no`, `cycle_no`, `period_no`),
  KEY `idx_membership_token_grant_user_id` (`user_id`),
  KEY `idx_membership_token_grant_order_no` (`order_no`),
  KEY `idx_membership_token_grant_status` (`status`),
  KEY `idx_membership_token_grant_scheduled_at` (`scheduled_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='会员Token基础额度与周五补给计划表';
