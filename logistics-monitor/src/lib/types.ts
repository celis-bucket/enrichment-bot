export interface Company {
  company_id: string
  ig_username: string
  name: string
  ig_url: string
  country: string
  is_active: boolean
  website_url: string | null
  scan_id: string | null
  scanned_at: string | null
  status: string | null
  risk_score: number | null
  risk_level: string | null
  recency_trend: string | null
  complaints_found: number | null
  comments_analyzed: number | null
  complaint_rate_pct: number | null
  ig_followers: number | null
  summary: string | null
  score_delta: number | null
  prev_risk_score: number | null
  category_breakdown: CategoryBreakdown | null
}

export interface CategoryBreakdown {
  DELAY: number
  NON_DELIVERY: number
  DAMAGED: number
  WRONG_ITEM: number
  RETURN_REFUND: number
  POOR_SERVICE: number
}

export interface Scan {
  id: string
  company_id: string
  scanned_at: string
  status: string
  risk_score: number | null
  risk_level: string | null
  summary: string | null
  posts_analyzed: number | null
  total_comments_scraped: number | null
  brand_replies_excluded: number | null
  comments_analyzed: number | null
  complaints_found: number | null
  complaint_rate_pct: number | null
  category_breakdown: CategoryBreakdown | null
  recency_trend: string | null
  recent_complaint_rate: number | null
  older_complaint_rate: number | null
  ig_followers: number | null
  runtime_sec: number | null
  claude_tokens_used: number | null
  error_message: string | null
  prev_risk_score: number | null
  score_delta: number | null
}

export interface FlaggedComment {
  id: string
  scan_id: string
  company_id: string
  comment_id: string
  text: string
  category: string
  severity: string
  owner: string
  comment_timestamp: string
  likes: number
  post_url: string
}

export type RiskLevel = 'none' | 'low' | 'medium' | 'high' | 'critical'
export type Trend = 'worsening' | 'stable' | 'improving'
