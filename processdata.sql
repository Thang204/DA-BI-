-- 1. TỔNG QUAN BẢNG: số dòng, khoảng thời gian, số khách hàng
-- ---------------------------------------------------------------------
SELECT
  COUNT(*) AS total_rows,
  COUNT(DISTINCT order_id) AS distinct_order_ids,
  COUNT(DISTINCT customer_id) AS distinct_customers,
  MIN(( order_date))              AS min_order_date,
  MAX(( order_date))              AS max_order_date
FROM `nimble-cortex-417611.ECommerce.Sales`;


-- ---------------------------------------------------------------------
-- 2. KIỂM TRA TRÙNG LẶP (Primary key: order_id)
-- ---------------------------------------------------------------------
-- 2a. order_id có bị lặp không?
SELECT
  order_id,
  COUNT(*) AS cnt
FROM `nimble-cortex-417611.ECommerce.Sales`
GROUP BY order_id
HAVING COUNT(*) > 1;

-- 2b. Có dòng nào trùng lặp hoàn toàn (full duplicate) không?
SELECT
  order_id, order_date, customer_id, product_category, region,
  quantity, unit_price, discount, payment_method, delivery_days,
  customer_rating, revenue,
  COUNT(*) AS cnt
FROM `nimble-cortex-417611.ECommerce.Sales`
GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12
HAVING COUNT(*) > 1;


-- ---------------------------------------------------------------------
-- 3. KIỂM TRA NULL / MISSING trên toàn bộ cột
-- ---------------------------------------------------------------------
SELECT
  COUNTIF(order_id IS NULL)         AS null_order_id,
  COUNTIF(order_date IS NULL)       AS null_order_date,
  COUNTIF(customer_id IS NULL)      AS null_customer_id,
  COUNTIF(product_category IS NULL) AS null_product_category,
  COUNTIF(region IS NULL)           AS null_region,
  COUNTIF(quantity IS NULL)         AS null_quantity,
  COUNTIF(unit_price IS NULL)       AS null_unit_price,
  COUNTIF(discount IS NULL)         AS null_discount,
  COUNTIF(payment_method IS NULL)   AS null_payment_method,
  COUNTIF(delivery_days IS NULL)    AS null_delivery_days,
  COUNTIF(customer_rating IS NULL)  AS null_customer_rating,
  COUNTIF(revenue IS NULL)          AS null_revenue,
  COUNT(*)                          AS total_rows
FROM `nimble-cortex-417611.ECommerce.Sales`;


-- ---------------------------------------------------------------------
-- 4. PHÂN BỐ GIÁ TRỊ CÁC CỘT PHÂN LOẠI (dimension) — phát hiện lỗi chính tả,
--    sai định dạng (vd: "south" vs "South", khoảng trắng thừa...)
-- ---------------------------------------------------------------------
SELECT product_category, COUNT(*) AS cnt
FROM `nimble-cortex-417611.ECommerce.Sales`
GROUP BY product_category
ORDER BY cnt DESC;

SELECT region, COUNT(*) AS cnt
FROM `nimble-cortex-417611.ECommerce.Sales`
GROUP BY region
ORDER BY cnt DESC;

SELECT payment_method, COUNT(*) AS cnt
FROM `nimble-cortex-417611.ECommerce.Sales`
GROUP BY payment_method
ORDER BY cnt DESC;

-- Kiểm tra khoảng trắng thừa / khác biệt case ẩn (nếu trả về dòng => có lỗi format)
SELECT DISTINCT product_category
FROM `nimble-cortex-417611.ECommerce.Sales`
WHERE product_category != TRIM(product_category)
   OR product_category != INITCAP(product_category);


-- ---------------------------------------------------------------------
-- 5. KIỂM TRA KHOẢNG GIÁ TRỊ (range check) CÁC CỘT SỐ
--    Kỳ vọng (theo phân tích sơ bộ từ file gốc):
--    quantity: 1–7 | discount: 0–0.35 | customer_rating: 1–5 |
--    delivery_days: 1–11 | unit_price, revenue: dương
-- ---------------------------------------------------------------------
SELECT
  MIN(quantity)  AS min_qty,  MAX(quantity)  AS max_qty,
  MIN(unit_price)  AS min_price,      MAX(unit_price)  AS max_price,
  MIN(discount)  AS min_discount,   MAX(discount)  AS max_discount,
  MIN(delivery_days)  AS min_delivery,   MAX(delivery_days)  AS max_delivery,
  MIN(customer_rating) AS min_rating,     MAX(customer_rating)  AS max_rating,
  MIN(revenue)  AS min_revenue, MAX(revenue) AS max_revenue
FROM `nimble-cortex-417611.ECommerce.Sales`;

-- Dòng vi phạm business rule (số âm, discount > 1, rating ngoài 1-5...)
SELECT *
FROM `nimble-cortex-417611.ECommerce.Sales`
WHERE quantity <= 0
   OR unit_price <= 0
   OR discount < 0 OR discount > 1
   OR delivery_days <= 0
   OR customer_rating < 1 OR customer_rating > 5
   OR revenue < 0;


-- ---------------------------------------------------------------------
-- 6. KIỂM TRA NHẤT QUÁN CÔNG THỨC: revenue = quantity * unit_price * (1 - discount)
--    (Ghi chú: trên bộ dữ liệu gốc công thức này khớp 100%, nhưng vẫn nên
--    kiểm tra lại trên bảng BigQuery của bạn để chắc chắn quá trình load
--    không làm sai lệch số liệu.)
-- ---------------------------------------------------------------------
SELECT
  order_id, quantity, unit_price, discount, revenue,
  ROUND(quantity * unit_price * (1 - discount), 2) AS calculated_revenue,
  ROUND(ABS(revenue - quantity * unit_price * (1 - discount)), 2) AS diff
FROM `nimble-cortex-417611.ECommerce.Sales`
WHERE ABS(revenue - quantity * unit_price * (1 - discount)) > 0.5
ORDER BY diff DESC;

-- =====================================================================
-- 8. TẠO BẢNG/VIEW ĐÃ LÀM SẠCH (cleaned layer)
--    - Parse order_date thành DATE thật
--    - Chuẩn hoá text (TRIM, chuẩn hoá case) cho các cột phân loại
--    - Loại bỏ trùng lặp hoàn toàn (nếu có)
--    - Thêm cột tính toán hữu ích cho phân tích/dashboard
-- =====================================================================
CREATE OR REPLACE VIEW `nimble-cortex-417611.ECommerce.Sales_clean` AS
WITH dedup AS (
  SELECT *,
    ROW_NUMBER() OVER (
      PARTITION BY order_id
      ORDER BY order_date
    ) AS rn
  FROM `nimble-cortex-417611.ECommerce.Sales`
)
SELECT
  order_id,
  order_date,
  customer_id,
  TRIM(INITCAP(product_category)) AS product_category,
  TRIM(INITCAP(region))  AS region,
  quantity,
  ROUND(unit_price, 2)   AS unit_price,
  discount,
  TRIM(UPPER(payment_method)) AS payment_method,
  delivery_days,
  customer_rating,
  ROUND(revenue, 2)   AS revenue,
  -- Cột phái sinh phục vụ phân tích:
  ROUND(unit_price * (1 - discount), 2) AS effective_unit_price,
  
  CASE
    WHEN customer_rating >= 4 THEN 'Positive'
    WHEN customer_rating >= 3 THEN 'Neutral'
    ELSE 'Negative'
  END AS rating_segment,
  CASE
    WHEN delivery_days <= 3 THEN 'Fast (<=3d)'
    WHEN delivery_days <= 7 THEN 'Standard (4-7d)'
    ELSE 'Slow (8d+)'
  END AS delivery_segment
FROM dedup
WHERE rn = 1;  -- loại bỏ trùng lặp order_id (giữ bản ghi đầu tiên)

-- Kiểm tra nhanh sau khi tạo view:
SELECT COUNT(*) AS total_rows_clean
FROM `nimble-cortex-417611.ECommerce.Sales_clean`;