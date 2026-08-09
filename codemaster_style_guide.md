# CodeMaster Modern Python & Security Coding Standard (2025/2026)

## 1. Timezone & Datetime Standards
- DEPRECATED: datetime.utcnow()
- REQUIRED: from datetime import datetime, timezone; datetime.now(timezone.utc)

## 2. JWT & Auth Security
- DEPRECATED: python-jose
- REQUIRED: PyJWT (import jwt)
- Standard Decode:
  payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])

## 3. Concurrency & Rate Limiters
- Lock Pattern Rules:
  class SafeRateLimiter:
      def __init__(self):
          self._lock = threading.Lock()
          
      def _refill_unlocked(self, now):
          pass

      def allow_request(self):
          with self._lock:
              self._refill_unlocked(time.time())

## 4. Pandas Rolling Windows
- Incorrect (Row-based): df['sales'].rolling(window=7).sum()
- Correct (Time-based): df.set_index('date').resample('D').sum().rolling('7D').sum()
