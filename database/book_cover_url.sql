ALTER TABLE `books`
  ADD COLUMN `coverUrl` VARCHAR(512) NULL DEFAULT NULL
  COMMENT '书籍封面图片地址'
  AFTER `description`;
