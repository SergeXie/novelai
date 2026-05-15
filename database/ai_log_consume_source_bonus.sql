ALTER TABLE `ai_novel_generate_log`
  MODIFY COLUMN `consumeSource` VARCHAR(32) NOT NULL DEFAULT 'free'
  COMMENT '消费来源：free/monthly/bonus/permanent/mixed/system';
