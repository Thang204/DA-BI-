import numpy as np 
import pandas as pd 
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
from scipy import stats
warnings.filterwarnings('ignore')
from statsmodels.tsa.holtwinters import ExponentialSmoothing 
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import r2_score, mean_absolute_error
pd.set_option("display.width", 120)


df = pd.read_csv("c:/Users/Admin/Downloads/E-Commerce Sales Analytics.csv")
print(df.head())
print(df.tail())
print(df.shape)
print(df.columns)
print(df.dtypes)
print(df.info())
print(df.isnull().sum())
print(df.duplicated().sum())
print(df.describe())


def show_fig():
    plt.tight_layout()
    plt.show()

plot_no = 1
fig = plt.figure(figsize=(10,6))
sns.histplot(data=df, x='revenue', kde=True)
plt.title(f'{plot_no}. Revenue Distribution and Overall Sales Concentration')
show_fig()
plot_no += 1


print("\n" + "=" * 70)
print("1. RFM SEGMENTATION")
print("=" * 70)
 
snapshot_date = df["order_date"].max() + pd.Timedelta(days=1)
 
rfm = df.groupby("customer_id").agg(
    recency_days=("order_date", lambda x: (snapshot_date - x.max()).days),
    frequency=("order_id", "count"),
    monetary=("revenue", "sum"),
).reset_index()
 
# Chấm điểm 1-5 theo quintile (5 = tốt nhất)
# Recency: càng nhỏ càng tốt -> đảo ngược thang điểm
rfm["R_score"] = pd.qcut(rfm["recency_days"], 5, labels=[5, 4, 3, 2, 1]).astype(int)
rfm["F_score"] = pd.qcut(rfm["frequency"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
rfm["M_score"] = pd.qcut(rfm["monetary"], 5, labels=[1, 2, 3, 4, 5]).astype(int)
rfm["RFM_score"] = rfm["R_score"] + rfm["F_score"] + rfm["M_score"]
 
def segment_customer(row):
    r, f, m = row["R_score"], row["F_score"], row["M_score"]
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    elif r >= 3 and f >= 3:
        return "Loyal Customers"
    elif r >= 4 and f <= 2:
        return "New Customers"
    elif r <= 2 and f >= 3 and m >= 3:
        return "At Risk"
    elif r <= 2 and f <= 2 and m <= 2:
        return "Lost / Hibernating"
    else:
        return "Need Attention"
 
rfm["rfm_segment"] = rfm.apply(segment_customer, axis=1)
 
segment_summary = rfm.groupby("rfm_segment").agg(
    customers=("customer_id", "count"),
    avg_recency=("recency_days", "mean"),
    avg_frequency=("frequency", "mean"),
    avg_monetary=("monetary", "mean"),
    total_monetary=("monetary", "sum"),
).round(1).sort_values("total_monetary", ascending=False)
segment_summary["pct_customers"] = (segment_summary["customers"] / segment_summary["customers"].sum() * 100).round(1)
segment_summary["pct_revenue"] = (segment_summary["total_monetary"] / segment_summary["total_monetary"].sum() * 100).round(1)
 
print(segment_summary)
 
rfm.to_csv("/mnt/user-data/outputs/rfm_customer_segments.csv", index=False)
segment_summary.reset_index().to_csv("/mnt/user-data/outputs/rfm_segment_summary.csv", index=False)
 
 
# =======================================================================
# 2. STATISTICAL TESTING
# =======================================================================
print("\n" + "=" * 70)
print("2. KIỂM ĐỊNH THỐNG KÊ")
print("=" * 70)
 
# 2.1 ANOVA: rating có khác nhau có ý nghĩa giữa các product_category không?
groups = [g["customer_rating"].values for _, g in df.groupby("product_category")]
f_stat, p_value = stats.f_oneway(*groups)
print(f"\n[ANOVA] Rating khác nhau giữa các Product Category?")
print(f"  F-statistic = {f_stat:.3f}, p-value = {p_value:.4f}")
print(f"  => {'CÓ ý nghĩa thống kê (p<0.05)' if p_value < 0.05 else 'KHÔNG có ý nghĩa thống kê (p>=0.05), khác biệt có thể do ngẫu nhiên'}")
 
# 2.2 ANOVA: rating có khác nhau giữa các region không?
groups_region = [g["customer_rating"].values for _, g in df.groupby("region")]
f_stat_r, p_value_r = stats.f_oneway(*groups_region)
print(f"\n[ANOVA] Rating khác nhau giữa các Region?")
print(f"  F-statistic = {f_stat_r:.3f}, p-value = {p_value_r:.4f}")
print(f"  => {'CÓ ý nghĩa thống kê' if p_value_r < 0.05 else 'KHÔNG có ý nghĩa thống kê'}")
 
# 2.3 T-test: rating giao hàng nhanh (<=3 ngày) vs giao chậm (8+ ngày)
fast = df[df["delivery_days"] <= 3]["customer_rating"]
slow = df[df["delivery_days"] >= 8]["customer_rating"]
t_stat, p_val_t = stats.ttest_ind(fast, slow, equal_var=False)
print(f"\n[T-TEST] Rating: Giao nhanh (<=3d, n={len(fast)}) vs Giao chậm (8d+, n={len(slow)})")
print(f"  Avg rating nhanh = {fast.mean():.2f} | Avg rating chậm = {slow.mean():.2f}")
print(f"  t-statistic = {t_stat:.3f}, p-value = {p_val_t:.4f}")
print(f"  => {'CÓ khác biệt ý nghĩa thống kê' if p_val_t < 0.05 else 'KHÔNG có khác biệt ý nghĩa thống kê'}")
 
# 2.4 Pearson correlation với p-value: discount vs rating, discount vs quantity
corr_dr, p_dr = stats.pearsonr(df["discount"], df["customer_rating"])
corr_dq, p_dq = stats.pearsonr(df["discount"], df["quantity"])
corr_del_r, p_del_r = stats.pearsonr(df["delivery_days"], df["customer_rating"])
print(f"\n[CORRELATION]")
print(f"  Discount vs Rating:      r={corr_dr:.3f}, p={p_dr:.4f} -> {'có ý nghĩa' if p_dr<0.05 else 'không có ý nghĩa'}")
print(f"  Discount vs Quantity:    r={corr_dq:.3f}, p={p_dq:.4f} -> {'có ý nghĩa' if p_dq<0.05 else 'không có ý nghĩa'}")
print(f"  Delivery Days vs Rating: r={corr_del_r:.3f}, p={p_del_r:.4f} -> {'có ý nghĩa' if p_del_r<0.05 else 'không có ý nghĩa'}")
 
stat_results = pd.DataFrame([
    {"test": "ANOVA - Rating by Category", "statistic": f_stat, "p_value": p_value, "significant": p_value < 0.05},
    {"test": "ANOVA - Rating by Region", "statistic": f_stat_r, "p_value": p_value_r, "significant": p_value_r < 0.05},
    {"test": "T-test - Fast vs Slow Delivery Rating", "statistic": t_stat, "p_value": p_val_t, "significant": p_val_t < 0.05},
    {"test": "Correlation - Discount vs Rating", "statistic": corr_dr, "p_value": p_dr, "significant": p_dr < 0.05},
    {"test": "Correlation - Discount vs Quantity", "statistic": corr_dq, "p_value": p_dq, "significant": p_dq < 0.05},
    {"test": "Correlation - Delivery Days vs Rating", "statistic": corr_del_r, "p_value": p_del_r, "significant": p_del_r < 0.05},
])
stat_results.to_csv("/mnt/user-data/outputs/statistical_test_results.csv", index=False)
 
 
# =======================================================================
# 3. REVENUE FORECASTING (6 tháng tới)
# =======================================================================
print("\n" + "=" * 70)
print("3. DỰ BÁO DOANH THU (Holt-Winters Exponential Smoothing)")
print("=" * 70)
 
monthly_rev = df.set_index("order_date").resample("MS")["revenue"].sum()
monthly_rev = monthly_rev.asfreq("MS")
 
model = ExponentialSmoothing(
    monthly_rev, trend="add", seasonal="add", seasonal_periods=12
).fit()
 
forecast_periods = 6
forecast = model.forecast(forecast_periods)
 
forecast_df = pd.DataFrame({
    "year_month": forecast.index.strftime("%Y-%m"),
    "forecast_revenue": forecast.values.round(2),
    "type": "forecast"
})
history_df = pd.DataFrame({
    "year_month": monthly_rev.index.strftime("%Y-%m"),
    "forecast_revenue": monthly_rev.values.round(2),
    "type": "actual"
})
combined_forecast = pd.concat([history_df, forecast_df], ignore_index=True)
combined_forecast.to_csv("/mnt/user-data/outputs/revenue_forecast.csv", index=False)
 
print(forecast_df.to_string(index=False))
print(f"\n(Đã lưu full lịch sử + forecast vào revenue_forecast.csv)")
 
print("\n" + "=" * 70)
print("HOÀN TẤT. Các file output đã lưu ở /mnt/user-data/outputs/:")
print("  - rfm_customer_segments.csv   (chi tiết từng khách hàng + segment)")
print("  - rfm_segment_summary.csv     (tổng hợp theo segment)")
print("  - statistical_test_results.csv")
print("  - revenue_forecast.csv        (actual + forecast 6 tháng)")
print("=" * 70)
 
