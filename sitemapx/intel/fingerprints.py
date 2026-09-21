from __future__ import annotations

from dataclasses import dataclass
import re
import socket

try:
    import dns.resolver
except Exception:
    dns = None


@dataclass(slots=True)
class Fingerprint:
    category: str
    name: str
    confidence: float
    evidence: str


PATTERNS = [
    ("Framework", "Next.js", .98, [r"/_next/", r"__NEXT_DATA__"]),
    ("Framework", "Nuxt", .97, [r"/_nuxt/", r"__NUXT__"]),
    ("Framework", "SvelteKit", .96, [r"__SVELTEKIT", r"/_app/immutable/"]),
    ("Framework", "Remix", .92, [r"__remixManifest", r"/build/.*\.js"]),
    ("Framework", "Gatsby", .96, [r"___gatsby", r"gatsby-script"]),
    ("Framework", "Astro", .92, [r"astro-island", r"/_astro/"]),
    ("Framework", "Angular", .90, [r"ng-version=", r"angular"]),
    ("Framework", "React", .75, [r"react(?:\.production)?\.min\.js", r"data-reactroot"]),
    ("Framework", "Vue", .78, [r"vue(?:\.runtime)?", r"data-v-"]),
    ("Framework", "Ember", .80, [r"ember-view", r"ember-source"]),
    ("CMS", "WordPress", .98, [r"/wp-content/", r"/wp-includes/"]),
    ("CMS", "Drupal", .92, [r"drupalSettings", r"/sites/default/files/"]),
    ("CMS", "Joomla", .88, [r"/media/system/js/", r"option=com_"]),
    ("CMS", "Ghost", .92, [r"ghost/api", r"generator[^>]+Ghost"]),
    ("CMS", "Contentful", .90, [r"contentful\.com"]),
    ("CMS", "Sanity", .90, [r"sanity\.io", r"cdn\.sanity\.io"]),
    ("Backend", "Django", .86, [r"csrftoken", r"csrfmiddlewaretoken"]),
    ("Backend", "Rails", .84, [r"_rails_session", r"csrf-param"]),
    ("Backend", "Laravel", .88, [r"XSRF-TOKEN", r"laravel_session"]),
    ("Backend", "ASP.NET", .90, [r"ASP\.NET", r"__VIEWSTATE", r"\.AspNetCore\."]),
    ("Backend", "Spring Boot", .80, [r"Whitelabel Error Page", r"JSESSIONID"]),
    ("CDN", "Cloudflare", .98, [r"cf-ray", r"__cf_bm"]),
    ("CDN", "Fastly", .94, [r"x-served-by", r"fastly"]),
    ("CDN", "CloudFront", .95, [r"x-amz-cf-id", r"cloudfront"]),
    ("Analytics", "GA4", .94, [r"googletagmanager\.com/gtag/js", r"G-[A-Z0-9]{6,}"]),
    ("Analytics", "Google Tag Manager", .94, [r"googletagmanager\.com/gtm\.js", r"GTM-[A-Z0-9]+"]),
    ("Analytics", "Mixpanel", .92, [r"mixpanel"]),
    ("Analytics", "Segment", .90, [r"segment\.com", r"analytics\.load"]),
    ("Analytics", "Amplitude", .92, [r"amplitude"]),
    ("Auth", "Auth0", .94, [r"auth0\.com", r"auth0-spa-js"]),
    ("Auth", "Okta", .94, [r"okta\.com", r"okta-auth-js"]),
    ("Auth", "Firebase Auth", .90, [r"firebaseapp\.com", r"firebase/auth"]),
    ("Auth", "Cognito", .90, [r"amazoncognito", r"cognito-idp"]),
    ("Auth", "Clerk", .92, [r"clerk\.com", r"clerk-js"]),
    ("Auth", "Supabase Auth", .92, [r"supabase\.co", r"supabase-js"]),
    ("Payments", "Stripe", .97, [r"js\.stripe\.com", r"stripe"]),
    ("Payments", "PayPal", .95, [r"paypal\.com/sdk/js"]),
    ("Payments", "Braintree", .94, [r"braintree"]),
    ("Payments", "Adyen", .94, [r"adyen"]),
    ("Error tracking", "Sentry", .95, [r"sentry\.io", r"Sentry\.init"]),
    ("Error tracking", "Rollbar", .92, [r"rollbar"]),
    ("Error tracking", "Bugsnag", .92, [r"bugsnag"]),
    ("Error tracking", "Datadog RUM", .92, [r"datadogRum", r"browser-intake-datadoghq"]),
    ("Infra hint", "PostgreSQL", .82, [r"psycopg", r"PostgreSQL", r"PG::[A-Za-z]+"]),
    ("Infra hint", "MySQL", .82, [r"MySQL", r"mysqli?_[a-z]+", r"SQLSTATE\[HY000\]"]),
    ("Infra hint", "MongoDB", .82, [r"Mongo(?:DB|ServerError|NetworkError)", r"mongodb://"]),
    ("Infra hint", "Redis", .80, [r"Redis(?:Error|Connection)", r"redis://"]),
    ("Infra hint", "Kubernetes", .78, [r"kubernetes", r"k8s", r"pod/[A-Za-z0-9._-]+"]),
]


def fingerprint(headers: dict[str, str], text: str, cookies: list[str] | None = None, url: str = "") -> list[Fingerprint]:
    lower_headers = {k.lower(): v for k, v in headers.items()}
    hay = "\n".join([url, text[:2_000_000], "\n".join(f"{k}:{v}" for k, v in lower_headers.items()), " ".join(cookies or [])])
    out: list[Fingerprint] = []
    if lower_headers.get("server"):
        out.append(Fingerprint("Web server", lower_headers["server"], .99, f"Server: {lower_headers['server']}"))
    if lower_headers.get("x-powered-by"):
        out.append(Fingerprint("Backend", lower_headers["x-powered-by"], .93, f"X-Powered-By: {lower_headers['x-powered-by']}"))
    if "express" in lower_headers.get("x-powered-by", "").lower():
        out.append(Fingerprint("Backend", "Express", .98, "X-Powered-By: Express"))
    if "akamai" in hay.lower() or "x-akamai" in hay.lower():
        out.append(Fingerprint("CDN", "Akamai", .92, "Akamai header/content marker"))
    for category, name, confidence, patterns in PATTERNS:
        for pat in patterns:
            m = re.search(pat, hay, re.I)
            if m:
                evidence = m.group(0)[:180]
                out.append(Fingerprint(category, name, confidence, evidence))
                break
    dedup = {}
    for fp in out:
        key = (fp.category, fp.name)
        if key not in dedup or fp.confidence > dedup[key].confidence:
            dedup[key] = fp
    return list(dedup.values())


def dns_fingerprints(host: str) -> list[Fingerprint]:
    host = (host or "").strip(".")
    if not host:
        return []
    names: list[str] = []
    try:
        if dns is not None:
            for answer in dns.resolver.resolve(host, "CNAME", lifetime=3.0):
                names.append(str(answer.target).rstrip("."))
    except Exception:
        pass
    if not names:
        try:
            canonical, aliases, _ = socket.gethostbyname_ex(host)
            names.extend([canonical, *aliases])
        except Exception:
            pass
    out: list[Fingerprint] = []
    providers = [
        ("CloudFront", ("cloudfront.net",)),
        ("Fastly", ("fastly.net", "fastlylb.net")),
        ("Akamai", ("akamai", "akamaiedge.net", "edgesuite.net")),
        ("Cloudflare", ("cloudflare", "cdn.cloudflare.net")),
    ]
    for name in dict.fromkeys(names):
        low = name.lower()
        for provider, needles in providers:
            if any(n in low for n in needles):
                out.append(Fingerprint("CDN", provider, .94, f"DNS CNAME/canonical target: {name}"))
    return out
