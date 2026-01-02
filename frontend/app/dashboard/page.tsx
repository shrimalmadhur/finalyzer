"use client";

import { useState, useEffect } from "react";
import {
  DollarSign,
  CreditCard,
  ArrowUpRight,
  ArrowDownRight,
  BarChart3,
  PieChart,
  Activity,
  Receipt,
  CalendarRange,
  Loader2,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart as RechartsPie,
  Pie,
  Cell,
  AreaChart,
  Area,
} from "recharts";
import { api } from "@/lib/api";
import type {
  DashboardOverview,
  CategorySpending,
  MonthlySpending,
  YearComparison,
  TopMerchant,
  SourceSpending,
  DailySpending,
} from "@/lib/api";
import clsx from "clsx";
import { usePrivacy } from "@/contexts/PrivacyContext";

// Premium color palette
const COLORS = [
  "#1acd8a", // jade
  "#3b82f6", // blue
  "#f59e0b", // amber
  "#8b5cf6", // violet
  "#ec4899", // pink
  "#06b6d4", // cyan
  "#ef4444", // red
  "#84cc16", // lime
  "#6366f1", // indigo
  "#14b8a6", // teal
];

const CATEGORY_COLORS: Record<string, string> = {
  "Food & Dining": "#f59e0b",
  Shopping: "#ec4899",
  Transportation: "#3b82f6",
  Entertainment: "#8b5cf6",
  "Bills & Utilities": "#eab308",
  Travel: "#06b6d4",
  Health: "#ef4444",
  Groceries: "#1acd8a",
  Gas: "#f97316",
  Subscriptions: "#6366f1",
  Income: "#22c55e",
  Transfer: "#64748b",
  Other: "#9ca3af",
  Uncategorized: "#6b7280",
};

type TabType = "overview" | "categories" | "trends" | "comparison";

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<TabType>("overview");
  const [loading, setLoading] = useState(true);
  const [selectedYear, setSelectedYear] = useState<number | undefined>();
  const { isHidden, formatAmount } = usePrivacy();

  // Data states
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [categorySpending, setCategorySpending] =
    useState<CategorySpending | null>(null);
  const [monthlySpending, setMonthlySpending] =
    useState<MonthlySpending | null>(null);
  const [yearComparison, setYearComparison] = useState<YearComparison | null>(
    null
  );
  const [topMerchants, setTopMerchants] = useState<TopMerchant[]>([]);
  const [sourceSpending, setSourceSpending] = useState<SourceSpending | null>(
    null
  );
  const [dailySpending, setDailySpending] = useState<DailySpending | null>(
    null
  );

  useEffect(() => {
    loadDashboardData();
  }, [selectedYear]);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const [
        overviewData,
        categoryData,
        monthlyData,
        yearData,
        merchantsData,
        sourceData,
        dailyData,
      ] = await Promise.all([
        api.getDashboardOverview(selectedYear),
        api.getSpendingByCategory(selectedYear),
        api.getMonthlySpending(selectedYear),
        api.getYearComparison(),
        api.getTopMerchants({ limit: 10, year: selectedYear }),
        api.getSpendingBySource(selectedYear),
        api.getDailySpending({ days: 30, year: selectedYear }),
      ]);

      setOverview(overviewData);
      setCategorySpending(categoryData);
      setMonthlySpending(monthlyData);
      setYearComparison(yearData);
      setTopMerchants(merchantsData.data);
      setSourceSpending(sourceData);
      setDailySpending(dailyData);
    } catch (error) {
      console.error("Failed to load dashboard data:", error);
    } finally {
      setLoading(false);
    }
  };

  const tabs = [
    { id: "overview" as const, label: "Overview", icon: BarChart3 },
    { id: "categories" as const, label: "Categories", icon: PieChart },
    { id: "trends" as const, label: "Trends", icon: Activity },
    { id: "comparison" as const, label: "Years", icon: CalendarRange },
  ];

  const formatCurrency = (value: number) => {
    if (isHidden) {
      return "••••••";
    }
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatMonth = (monthStr: string) => {
    const [year, month] = monthStr.split("-");
    const date = new Date(parseInt(year), parseInt(month) - 1);
    return date.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-4">
        <div className="relative">
          <div className="w-16 h-16 rounded-2xl bg-jade-500/10 flex items-center justify-center">
            <Loader2 className="w-8 h-8 text-jade-400 animate-spin" />
          </div>
          <div className="absolute inset-0 w-16 h-16 rounded-2xl bg-jade-500/20 blur-xl animate-pulse" />
        </div>
        <p className="text-midnight-400">Loading dashboard...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="animate-fade-up fill-both">
          <h1 className="font-display text-display-sm md:text-display-md tracking-tight">
            <span className="text-cream-100">Financial</span>{" "}
            <span className="gradient-text">Dashboard</span>
          </h1>
          <p className="text-midnight-400 mt-1">
            Analyze your spending patterns and trends
          </p>
        </div>

        {/* Year selector */}
        {yearComparison && yearComparison.data.length > 0 && (
          <div className="animate-fade-up fill-both delay-100">
            <select
              value={selectedYear || ""}
              onChange={(e) =>
                setSelectedYear(e.target.value ? parseInt(e.target.value) : undefined)
              }
              className="input-field w-auto min-w-[140px] py-2 text-sm"
            >
              <option value="">All Time</option>
              {yearComparison.data.map((y) => (
                <option key={y.year} value={y.year}>
                  {y.year}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Tab Navigation */}
      <div className="animate-fade-up fill-both delay-200">
        <div className="flex gap-2 p-1 rounded-2xl bg-ink-light/50 border border-white/[0.03] w-fit">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={clsx(
                  "relative flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-300",
                  activeTab === tab.id
                    ? "text-ink"
                    : "text-midnight-400 hover:text-cream-100"
                )}
              >
                {activeTab === tab.id && (
                  <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-jade-400 to-jade-500" />
                )}
                <span className="relative flex items-center gap-2">
                  <Icon className="w-4 h-4" />
                  <span className="hidden sm:inline">{tab.label}</span>
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Tab Content */}
      <div className="animate-fade-up fill-both delay-300">
        {activeTab === "overview" && (
          <OverviewTab
            overview={overview}
            categorySpending={categorySpending}
            topMerchants={topMerchants}
            sourceSpending={sourceSpending}
            dailySpending={dailySpending}
            formatCurrency={formatCurrency}
            isHidden={isHidden}
          />
        )}

        {activeTab === "categories" && (
          <CategoriesTab
            categorySpending={categorySpending}
            formatCurrency={formatCurrency}
            isHidden={isHidden}
          />
        )}

        {activeTab === "trends" && (
          <TrendsTab
            monthlySpending={monthlySpending}
            formatCurrency={formatCurrency}
            formatMonth={formatMonth}
            isHidden={isHidden}
          />
        )}

        {activeTab === "comparison" && (
          <ComparisonTab
            yearComparison={yearComparison}
            formatCurrency={formatCurrency}
            isHidden={isHidden}
          />
        )}
      </div>
    </div>
  );
}

// Custom tooltip component
function CustomTooltip({ active, payload, label, formatter }: any) {
  if (active && payload && payload.length) {
    return (
      <div className="glass-card rounded-xl p-3 shadow-lg border border-jade-500/10">
        <p className="text-xs text-midnight-400 mb-1">{label}</p>
        <p className="text-sm font-mono font-medium text-cream-100">
          {formatter ? formatter(payload[0].value) : payload[0].value}
        </p>
      </div>
    );
  }
  return null;
}

// Overview Tab
function OverviewTab({
  overview,
  categorySpending,
  topMerchants,
  sourceSpending,
  dailySpending,
  formatCurrency,
  isHidden,
}: {
  overview: DashboardOverview | null;
  categorySpending: CategorySpending | null;
  topMerchants: TopMerchant[];
  sourceSpending: SourceSpending | null;
  dailySpending: DailySpending | null;
  formatCurrency: (v: number) => string;
  isHidden: boolean;
}) {
  if (!overview) return null;

  const formatAxisValue = (v: number) => (isHidden ? "••••" : `$${(v / 1000).toFixed(0)}k`);
  const formatAxisValueSmall = (v: number) => (isHidden ? "••••" : `$${v}`);

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Spending"
          value={formatCurrency(overview.total_spending)}
          icon={DollarSign}
          gradient="from-jade-400 to-jade-600"
        />
        <StatCard
          title="Transactions"
          value={overview.total_transactions.toLocaleString()}
          icon={Receipt}
          gradient="from-blue-400 to-blue-600"
        />
        <StatCard
          title="Cards"
          value={overview.sources_count.toString()}
          icon={CreditCard}
          gradient="from-purple-400 to-purple-600"
        />
        <StatCard
          title="Categories"
          value={overview.categories_count.toString()}
          icon={PieChart}
          gradient="from-amber-400 to-amber-600"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Category Pie Chart */}
        <div className="glass-card rounded-2xl p-6">
          <h3 className="font-display text-lg font-semibold text-cream-100 mb-6">
            Spending by Category
          </h3>
          {categorySpending && categorySpending.data.length > 0 ? (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <RechartsPie>
                  <Pie
                    data={categorySpending.data.slice(0, 6)}
                    cx="50%"
                    cy="45%"
                    innerRadius={55}
                    outerRadius={90}
                    paddingAngle={3}
                    dataKey="amount"
                    nameKey="category"
                    strokeWidth={0}
                  >
                    {categorySpending.data.slice(0, 6).map((entry, index) => (
                      <Cell
                        key={entry.category}
                        fill={
                          CATEGORY_COLORS[entry.category] ||
                          COLORS[index % COLORS.length]
                        }
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    content={
                      <CustomTooltip formatter={formatCurrency} />
                    }
                  />
                </RechartsPie>
              </ResponsiveContainer>
              {/* Legend */}
              <div className="flex flex-wrap justify-center gap-3 mt-2">
                {categorySpending.data.slice(0, 6).map((entry, index) => (
                  <div
                    key={entry.category}
                    className="flex items-center gap-1.5"
                  >
                    <div
                      className="w-2.5 h-2.5 rounded-full"
                      style={{
                        backgroundColor:
                          CATEGORY_COLORS[entry.category] ||
                          COLORS[index % COLORS.length],
                      }}
                    />
                    <span className="text-xs text-midnight-300">
                      {entry.category}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="h-72 flex items-center justify-center text-midnight-400">
              No spending data available
            </div>
          )}
        </div>

        {/* Source Spending */}
        <div className="glass-card rounded-2xl p-6">
          <h3 className="font-display text-lg font-semibold text-cream-100 mb-6">
            Spending by Card
          </h3>
          {sourceSpending && sourceSpending.data.length > 0 ? (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={sourceSpending.data} layout="vertical">
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="rgba(142, 154, 154, 0.1)"
                    horizontal={false}
                  />
                  <XAxis
                    type="number"
                    tickFormatter={formatAxisValue}
                    stroke="#8e9a9a"
                    fontSize={12}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="source"
                    stroke="#8e9a9a"
                    width={80}
                    fontSize={12}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip content={<CustomTooltip formatter={formatCurrency} />} />
                  <Bar
                    dataKey="amount"
                    fill="url(#barGradient)"
                    radius={[0, 6, 6, 0]}
                  />
                  <defs>
                    <linearGradient id="barGradient" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="#1acd8a" />
                      <stop offset="100%" stopColor="#0fa96f" />
                    </linearGradient>
                  </defs>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-72 flex items-center justify-center text-midnight-400">
              No source data available
            </div>
          )}
        </div>
      </div>

      {/* Top Merchants */}
      <div className="glass-card rounded-2xl p-6">
        <h3 className="font-display text-lg font-semibold text-cream-100 mb-6">
          Top Merchants
        </h3>
        {topMerchants.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {topMerchants.map((merchant, index) => (
              <div
                key={merchant.merchant}
                className="flex items-center justify-between p-4 rounded-xl bg-ink-lighter/30 border border-white/[0.03] hover:border-jade-500/10 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span className="w-8 h-8 rounded-lg bg-jade-500/10 flex items-center justify-center text-sm font-medium text-jade-400">
                    {index + 1}
                  </span>
                  <div>
                    <p className="text-cream-100 font-medium text-sm truncate max-w-[180px]">
                      {merchant.merchant}
                    </p>
                    <p className="text-midnight-400 text-xs">
                      {merchant.count} transactions
                    </p>
                  </div>
                </div>
                <span className="text-red-400 font-mono text-sm font-medium">
                  {formatCurrency(merchant.amount)}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-midnight-400">
            No merchant data available
          </div>
        )}
      </div>

      {/* Daily Spending Chart */}
      <div className="glass-card rounded-2xl p-6">
        <h3 className="font-display text-lg font-semibold text-cream-100 mb-6">
          Last 30 Days
        </h3>
        {dailySpending && dailySpending.data.length > 0 ? (
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={dailySpending.data}>
                <defs>
                  <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#1acd8a" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#1acd8a" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(142, 154, 154, 0.1)"
                  vertical={false}
                />
                <XAxis
                  dataKey="date"
                  stroke="#8e9a9a"
                  tickFormatter={(d) => new Date(d).getDate().toString()}
                  fontSize={11}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  stroke="#8e9a9a"
                  tickFormatter={formatAxisValueSmall}
                  fontSize={11}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  content={
                    <CustomTooltip
                      formatter={formatCurrency}
                      label={(d: string) => new Date(d).toLocaleDateString()}
                    />
                  }
                />
                <Area
                  type="monotone"
                  dataKey="amount"
                  stroke="#1acd8a"
                  fill="url(#areaGradient)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="h-56 flex items-center justify-center text-midnight-400">
            No daily spending data available
          </div>
        )}
      </div>
    </div>
  );
}

// Categories Tab
function CategoriesTab({
  categorySpending,
  formatCurrency,
  isHidden,
}: {
  categorySpending: CategorySpending | null;
  formatCurrency: (v: number) => string;
  isHidden: boolean;
}) {
  if (!categorySpending || categorySpending.data.length === 0) {
    return (
      <div className="text-center py-16 text-midnight-400">
        No category data available. Upload some transactions first.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Pie Chart and Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass-card rounded-2xl p-6">
          <h3 className="font-display text-lg font-semibold text-cream-100 mb-6">
            Spending Distribution
          </h3>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <RechartsPie>
                <Pie
                  data={categorySpending.data}
                  cx="50%"
                  cy="50%"
                  innerRadius={65}
                  outerRadius={120}
                  paddingAngle={2}
                  dataKey="amount"
                  nameKey="category"
                  strokeWidth={0}
                >
                  {categorySpending.data.map((entry, index) => (
                    <Cell
                      key={entry.category}
                      fill={
                        CATEGORY_COLORS[entry.category] ||
                        COLORS[index % COLORS.length]
                      }
                    />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip formatter={formatCurrency} />} />
              </RechartsPie>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Category List */}
        <div className="glass-card rounded-2xl p-6">
          <h3 className="font-display text-lg font-semibold text-cream-100 mb-6">
            Category Breakdown
          </h3>
          <div className="space-y-4 max-h-80 overflow-y-auto pr-2">
            {categorySpending.data.map((item, index) => {
              const percentage = (item.amount / categorySpending.total) * 100;
              return (
                <div key={item.category}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{
                          backgroundColor:
                            CATEGORY_COLORS[item.category] ||
                            COLORS[index % COLORS.length],
                        }}
                      />
                      <span className="text-sm text-cream-100">
                        {item.category}
                      </span>
                    </div>
                    <span className="text-sm font-mono text-midnight-300">
                      {formatCurrency(item.amount)} {!isHidden && `(${percentage.toFixed(1)}%)`}
                    </span>
                  </div>
                  <div className="h-2 bg-ink-lighter rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-700 ease-out-expo"
                      style={{
                        width: `${percentage}%`,
                        backgroundColor:
                          CATEGORY_COLORS[item.category] || "#6b7280",
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

// Trends Tab
function TrendsTab({
  monthlySpending,
  formatCurrency,
  formatMonth,
  isHidden,
}: {
  monthlySpending: MonthlySpending | null;
  formatCurrency: (v: number) => string;
  formatMonth: (m: string) => string;
  isHidden: boolean;
}) {
  const formatAxisValue = (v: number) => (isHidden ? "••••" : `$${(v / 1000).toFixed(0)}k`);
  if (!monthlySpending || monthlySpending.data.length === 0) {
    return (
      <div className="text-center py-16 text-midnight-400">
        No trend data available. Upload some transactions first.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Monthly Bar Chart */}
      <div className="glass-card rounded-2xl p-6">
        <h3 className="font-display text-lg font-semibold text-cream-100 mb-6">
          Monthly Spending Trend
        </h3>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={monthlySpending.data}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(142, 154, 154, 0.1)"
                vertical={false}
              />
              <XAxis
                dataKey="month"
                tickFormatter={formatMonth}
                stroke="#8e9a9a"
                fontSize={11}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                stroke="#8e9a9a"
                tickFormatter={formatAxisValue}
                fontSize={11}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                content={<CustomTooltip formatter={formatCurrency} />}
                labelFormatter={formatMonth}
              />
              <Bar
                dataKey="spending"
                fill="url(#monthlyBarGradient)"
                radius={[6, 6, 0, 0]}
              />
              <defs>
                <linearGradient
                  id="monthlyBarGradient"
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop offset="0%" stopColor="#1acd8a" />
                  <stop offset="100%" stopColor="#0fa96f" />
                </linearGradient>
              </defs>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Monthly Summary Table */}
      <div className="glass-card rounded-2xl p-6">
        <h3 className="font-display text-lg font-semibold text-cream-100 mb-6">
          Monthly Summary
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-midnight-800">
                <th className="pb-4 text-left text-xs font-medium text-midnight-400 uppercase tracking-wider">
                  Month
                </th>
                <th className="pb-4 text-right text-xs font-medium text-midnight-400 uppercase tracking-wider">
                  Spending
                </th>
                <th className="pb-4 text-right text-xs font-medium text-midnight-400 uppercase tracking-wider">
                  Avg/Day
                </th>
                <th className="pb-4 text-right text-xs font-medium text-midnight-400 uppercase tracking-wider">
                  Txns
                </th>
              </tr>
            </thead>
            <tbody>
              {monthlySpending.data
                .slice(-12)
                .reverse()
                .map((month) => (
                  <tr
                    key={month.month}
                    className="border-b border-midnight-800/50 hover:bg-jade-500/[0.02]"
                  >
                    <td className="py-4 text-cream-100">
                      {formatMonth(month.month)}
                    </td>
                    <td className="py-4 text-right text-jade-400 font-mono">
                      {formatCurrency(month.spending)}
                    </td>
                    <td className="py-4 text-right text-midnight-300 font-mono">
                      {formatCurrency(month.spending / 30)}
                    </td>
                    <td className="py-4 text-right text-midnight-400">
                      {month.count}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// Comparison Tab
function ComparisonTab({
  yearComparison,
  formatCurrency,
  isHidden,
}: {
  yearComparison: YearComparison | null;
  formatCurrency: (v: number) => string;
  isHidden: boolean;
}) {
  if (!yearComparison || yearComparison.data.length === 0) {
    return (
      <div className="text-center py-16 text-midnight-400">
        No year comparison data available. Upload transactions from multiple
        years.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Year Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {yearComparison.data.map((year, idx) => (
          <div
            key={year.year}
            className="glass-card rounded-2xl p-6 border border-white/[0.04]"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-display text-2xl font-semibold text-cream-100">
                {year.year}
              </h3>
              {idx === 0 && (
                <span className="tag text-xs">Latest</span>
              )}
            </div>

            <p className="font-display text-3xl font-semibold text-jade-400 font-mono mb-1">
              {formatCurrency(year.spending)}
            </p>
            <p className="text-xs text-midnight-400 mb-4">Total spending</p>

            <div className="grid grid-cols-2 gap-4 pt-4 border-t border-midnight-800/50">
              <div>
                <p className="text-lg font-semibold text-cream-200">
                  {year.count.toLocaleString()}
                </p>
                <p className="text-xs text-midnight-400">Transactions</p>
              </div>
              <div>
                <p className="text-lg font-semibold text-cream-200 font-mono">
                  {formatCurrency(year.spending / 12)}
                </p>
                <p className="text-xs text-midnight-400">Avg/Month</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Year-over-Year Change */}
      {yearComparison.data.length >= 2 && (
        <div className="glass-card rounded-2xl p-6">
          <h3 className="font-display text-lg font-semibold text-cream-100 mb-6">
            Year-over-Year Comparison
          </h3>
          <div className="space-y-4">
            {yearComparison.data.slice(0, -1).map((year, idx) => {
              const prevYear = yearComparison.data[idx + 1];
              const diff = year.spending - prevYear.spending;
              const percentChange =
                prevYear.spending > 0
                  ? (diff / prevYear.spending) * 100
                  : 0;
              const isIncrease = diff > 0;
              const displayPercent =
                Math.abs(percentChange) > 500
                  ? isIncrease
                    ? ">500"
                    : "<-500"
                  : percentChange.toFixed(1);

              return (
                <div
                  key={year.year}
                  className="p-4 rounded-xl bg-ink-lighter/30 border border-white/[0.03]"
                >
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-lg font-medium text-cream-100">
                      {year.year} vs {prevYear.year}
                    </span>
                    <span
                      className={clsx(
                        "flex items-center gap-1 px-3 py-1 rounded-lg text-sm font-medium",
                        isHidden
                          ? "bg-midnight-800 text-midnight-400"
                          : isIncrease
                            ? "bg-red-500/10 text-red-400"
                            : "bg-jade-500/10 text-jade-400"
                      )}
                    >
                      {!isHidden && (isIncrease ? (
                        <ArrowUpRight className="w-4 h-4" />
                      ) : (
                        <ArrowDownRight className="w-4 h-4" />
                      ))}
                      {isHidden ? "••••" : `${displayPercent}%`}
                    </span>
                  </div>

                  {/* Visual comparison bars */}
                  <div className="space-y-2">
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-midnight-400 w-12">
                        {year.year}
                      </span>
                      <div className="flex-1 h-3 bg-ink-lighter rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-jade-500 to-jade-400 rounded-full transition-all duration-700"
                          style={{
                            width: `${Math.min(
                              100,
                              (year.spending /
                                Math.max(year.spending, prevYear.spending)) *
                                100
                            )}%`,
                          }}
                        />
                      </div>
                      <span className="text-xs font-mono text-jade-400 w-20 text-right">
                        {formatCurrency(year.spending)}
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-midnight-400 w-12">
                        {prevYear.year}
                      </span>
                      <div className="flex-1 h-3 bg-ink-lighter rounded-full overflow-hidden">
                        <div
                          className="h-full bg-jade-500/40 rounded-full transition-all duration-700"
                          style={{
                            width: `${Math.min(
                              100,
                              (prevYear.spending /
                                Math.max(year.spending, prevYear.spending)) *
                                100
                            )}%`,
                          }}
                        />
                      </div>
                      <span className="text-xs font-mono text-midnight-300 w-20 text-right">
                        {formatCurrency(prevYear.spending)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// Stat Card Component
function StatCard({
  title,
  value,
  icon: Icon,
  gradient,
}: {
  title: string;
  value: string;
  icon: React.ElementType;
  gradient: string;
}) {
  return (
    <div className="glass-card rounded-2xl p-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-midnight-400 uppercase tracking-wider mb-2">
            {title}
          </p>
          <p className="font-display text-2xl font-semibold text-cream-100">
            {value}
          </p>
        </div>
        <div
          className={`w-10 h-10 rounded-xl bg-gradient-to-br ${gradient} flex items-center justify-center shadow-glow`}
        >
          <Icon className="w-5 h-5 text-ink" />
        </div>
      </div>
    </div>
  );
}
