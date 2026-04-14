import os
import requests
import json

class TelegramNotifier:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        from utils.state_manager import state_manager
        from utils.logger import get_logger
        self.logger = get_logger("TelegramNotifier")
        
    def send_message(self, text, reply_markup=None):
        """Sends a text message with optional interactive buttons (Requirement 6)."""
        if not self.bot_token or not self.chat_id:
            self.logger.error("⚠️ Telegram Config Missing: check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env.local")
            return False
            
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": False,
            "parse_mode": "Markdown"
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)

        for attempt in range(3):
            try:
                response = requests.post(url, json=payload, timeout=8)
                if response.status_code == 200:
                    self.logger.info(f"✅ Telegram Delivery Success [Attempt {attempt+1}]")
                    from utils.state_manager import state_manager
                    import time
                    state_manager.update("last_telegram_time", time.time())
                    return True
                elif response.status_code == 429:
                    import time
                    time.sleep(2 ** attempt)
                else:
                    self.logger.warning(f"⚠️ Telegram API Error [{response.status_code}]: {response.text}")
            except Exception as e:
                self.logger.error(f"⚠️ Telegram attempt {attempt+1} failed: {e}")
                import time
                time.sleep(1)
        return False

    def verify_connectivity(self):
        """Startup Diagnostic: Verifies configuration and reachout (Requirement 4)."""
        if not self.bot_token or self.bot_token == "your_bot_token_here":
            return False, "Placeholder token detected in .env"
        
        url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                bot_name = data.get('result', {}).get('first_name', 'Unknown')
                return True, f"Connected to @{bot_name}"
            return False, f"API Error {resp.status_code}"
        except Exception as e:
            return False, str(e)

    def _classify_domain(self, title, skills):
        """Intelligent Domain Classification."""
        t = (title + " " + " ".join(skills)).lower()
        if any(w in t for w in ["fullstack", "full stack", "mern", "mean", "django + react"]):
            return "🌐 Full Stack"
        if any(w in t for w in ["frontend", "react", "vue", "angular", "ui", "ux", "web dev"]):
            return "🎨 Frontend"
        if any(w in t for w in ["backend", "python", "node", "django", "flask", "java", "golang", "api", "server"]):
            return "⚡ Backend"
        if any(w in t for w in ["data", "ml", "ai", "scientist", "analyst", "etl", "sql", "pytorch", "tensorflow"]):
            return "📊 Data & AI"
        return "📁 General IT"

    def format_job_card(self, job, is_compact=False):
        """Intelligent Assistant formatting (Requirements 2, 5, 6, 7)."""
        domain = job.get('domain') or self._classify_domain(job.get('title', ''), job.get('matched_skills', []))
        score = job.get('score', 0)
        source = job.get('source', 'Unknown Source').title()
        posted = job.get('posted_at', 'Today')
        gaps = job.get('metrics', {}).get('skill_gap', []) if isinstance(job.get('metrics'), dict) else []
        
        # Match Strength Logic
        if score >= 85: strength, tag = "💎 STRONG MATCH", "🔴 APPLY ASAP"
        elif score >= 70: strength, tag = "⭐ MODERATE", "🟡 OPTIONAL"
        else: strength, tag = "📌 DISCOVERY", "⚪ MONITOR"

        # Heading with score and domain
        header = f"🚀 *{job['title']}* ({score}%)\n"
        meta = f"🏢 {job['company']} | {domain}\n"
        transparency = f"📡 *Source:* {source} | ⏰ {posted}\n"
        
        if is_compact:
            return f"{header}{meta}{transparency}🔗 [View Details]({job['link']})\n"

        # v3.0 Structured Insights
        strengths = job.get('metrics', {}).get('strengths', []) if isinstance(job.get('metrics'), dict) else []
        risks = job.get('metrics', {}).get('risks', []) if isinstance(job.get('metrics'), dict) else []
        
        analysis_str = ""
        if strengths:
            analysis_str += f"\n✅ *Strengths:* {', '.join(strengths[:3])}"
        if risks:
            analysis_str += f"\n⚠️ *Risks:* {', '.join(risks[:2])}"

        gap_str = ""
        if gaps:
            gap_str = f"🧠 *Skill Gaps:* {', '.join(gaps)}\n"

        return (
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{header}"
            f"*{strength}* | {tag}\n\n"
            f"{meta}"
            f"📍 {job.get('location', 'Remote')}\n"
            f"📡 *Source:* {source}\n"
            f"⏰ *Posted:* {posted}\n\n"
            f"🛠️ *Matches:* {', '.join(job.get('matched_skills', [])[:3])}\n"
            f"{analysis_str}\n"
            f"{gap_str}"
        )

    def send_job_alert(self, job):
        """Interactive Job Card with Feedback Buttons (Requirement 1 & 4)."""
        card_text = self.format_job_card(job)
        job_id = job.get('id')
        
        reply_markup = {
            "inline_keyboard": [
                [{"text": "🚀 Apply Now", "url": job['link']}],
                [
                    {"text": "👎 Dismiss", "callback_data": f"ignore:{job_id}"},
                    {"text": "⭐ Save", "callback_data": f"save:{job_id}"},
                    {"text": "📝 Applied", "callback_data": f"applied:{job_id}"}
                ]
            ]
        }
        self.send_message(card_text, reply_markup=reply_markup)

    def send_summary(self, metrics, recommended_jobs=None, others=None):
        """Tiered Intelligence Summary with Compact Recap (v3.0)."""
        if metrics['total'] == 0:
            msg = (
                "💤 *Discovery Idle*\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "No new roles found. Monitoring enterprise portals for fresh opportunities..."
            )
            self.send_message(msg)
            return

        summary = [
            "⚡ *DIGEST REPORT* ⚡\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"🔍 *Roles Scanned:* {metrics['total']}\n"
            f"🎯 *Top Matches:* {metrics['rec']}\n"
            f"📂 *Others:* {metrics['others']}\n"
            "━━━━━━━━━━━━━━━━━━\n"
        ]

        if recommended_jobs:
            # Domain Grouping Logic (Requirement 5)
            by_domain = {}
            for job in recommended_jobs:
                domain = job.get('domain') or self._classify_domain(job['title'], job.get('matched_skills', []))
                if domain not in by_domain: by_domain[domain] = []
                by_domain[domain].append(f"• {job['title']} @ {job['company']}")

            summary.append("📍 *Top Tiers*")
            for domain, titles in by_domain.items():
                summary.append(f"*{domain}*\n" + "\n".join(titles[:3]))
            summary.append("━━━━━━━━━━━━━━━━━━\n")

        # compact recap for "Others" (Requirement: Anti-Spam)
        if others:
            summary.append("💡 *Compact Discovery*")
            for job in others[:5]:
                summary.append(f"• [{job['title']}]({job['link']}) @ {job['company']}")
            summary.append("━━━━━━━━━━━━━━━━━━\n")

        self.send_message("\n".join(summary))

# Singleton instance
notifier = TelegramNotifier()
