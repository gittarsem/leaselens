/**
 * LeaseBackground: Non-interactive architectural blueprint grid, residential skyline silhouette,
 * and ambient line-art watermarks tailored for LeaseLens.
 */
export function LeaseBackground() {
  return (
    <div
      className="pointer-events-none select-none fixed inset-0 overflow-hidden z-0"
      aria-hidden="true"
      style={{ zIndex: 0 }}
    >
      {/* 1. Subtle Architectural Blueprint Grid with radial vignette mask */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          backgroundImage: `
            linear-gradient(to right, rgba(255, 255, 255, 0.022) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(255, 255, 255, 0.022) 1px, transparent 1px)
          `,
          backgroundSize: '32px 32px',
          maskImage: 'radial-gradient(ellipse at 50% 45%, rgba(0, 0, 0, 1) 30%, rgba(0, 0, 0, 0.15) 75%, transparent 100%)',
          WebkitMaskImage: 'radial-gradient(ellipse at 50% 45%, rgba(0, 0, 0, 1) 30%, rgba(0, 0, 0, 0.15) 75%, transparent 100%)',
        }}
      />

      {/* 2. Ambient Corner Line-Art Watermark: Oversized House Key & Tag (Top-Right) */}
      <svg
        viewBox="0 0 320 320"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{
          position: 'absolute',
          top: -40,
          right: -40,
          width: 380,
          height: 380,
          opacity: 0.035,
          transform: 'rotate(22deg)',
        }}
      >
        {/* Keychain Ring */}
        <circle cx="160" cy="110" r="54" stroke="#ECEAE6" strokeWidth="2.5" />
        <circle cx="160" cy="110" r="42" stroke="#ECEAE6" strokeWidth="1.2" strokeDasharray="4 4" />
        {/* Key Bow */}
        <circle cx="210" cy="170" r="28" stroke="#F59E0B" strokeWidth="2.5" />
        <circle cx="210" cy="170" r="14" stroke="#F59E0B" strokeWidth="1.5" />
        {/* Key Stem & Bits */}
        <path d="M210 198V300H226V286H218V270H230V254H210" stroke="#F59E0B" strokeWidth="2.5" strokeLinejoin="round" />
        {/* Tag Silhouette */}
        <path
          d="M110 130L55 185C50 190 50 198 55 203L87 235C92 240 100 240 105 235L160 180L135 155Z"
          stroke="#34D399"
          strokeWidth="2"
        />
        <circle cx="138" cy="158" r="6" stroke="#34D399" strokeWidth="1.5" />
        {/* Tag text lines */}
        <line x1="85" y1="200" x2="120" y2="165" stroke="#34D399" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="95" y1="210" x2="130" y2="175" stroke="#34D399" strokeWidth="1.5" strokeLinecap="round" />
      </svg>

      {/* 3. Ambient Corner Line-Art Watermark: Signed Lease Scroll & Legal Seal (Bottom-Left) */}
      <svg
        viewBox="0 0 360 360"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{
          position: 'absolute',
          bottom: 40,
          left: -40,
          width: 420,
          height: 420,
          opacity: 0.032,
          transform: 'rotate(-10deg)',
        }}
      >
        {/* Folded Agreement Document */}
        <rect x="80" y="60" width="180" height="240" rx="8" stroke="#ECEAE6" strokeWidth="2" />
        <path d="M220 60V100H260" stroke="#ECEAE6" strokeWidth="1.8" />
        {/* Header bar */}
        <rect x="105" y="85" width="80" height="8" rx="2" stroke="#ECEAE6" strokeWidth="1.5" />
        {/* Clause rulings */}
        <line x1="105" y1="115" x2="235" y2="115" stroke="#ECEAE6" strokeWidth="1.5" />
        <line x1="105" y1="135" x2="235" y2="135" stroke="#ECEAE6" strokeWidth="1.5" />
        <line x1="105" y1="155" x2="215" y2="155" stroke="#ECEAE6" strokeWidth="1.5" />
        <line x1="105" y1="175" x2="235" y2="175" stroke="#ECEAE6" strokeWidth="1.5" />
        <line x1="105" y1="195" x2="195" y2="195" stroke="#ECEAE6" strokeWidth="1.5" />
        <line x1="105" y1="215" x2="235" y2="215" stroke="#ECEAE6" strokeWidth="1.5" />
        {/* Tenant signature curve */}
        <path d="M105 255Q125 240 145 255T185 250" stroke="#34D399" strokeWidth="2.2" strokeLinecap="round" />
        {/* Legal Authority Seal */}
        <circle cx="215" cy="255" r="24" stroke="#F59E0B" strokeWidth="2" />
        <circle cx="215" cy="255" r="19" stroke="#F59E0B" strokeWidth="1" strokeDasharray="3 3" />
        <path d="M215 242V268M202 255H228" stroke="#F59E0B" strokeWidth="1.5" />
        {/* Ribbon banner */}
        <path d="M205 275L215 268L225 275V290L215 284L205 290Z" stroke="#F59E0B" strokeWidth="1.2" />
      </svg>

      {/* 4. Minimalist Residential Apartment & Roofline Horizon SVG along bottom edge */}
      <svg
        viewBox="0 0 1600 240"
        preserveAspectRatio="none"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          width: '100%',
          height: 180,
          opacity: 0.6,
        }}
      >
        <defs>
          <linearGradient id="skyline-fade-back" x1="800" y1="40" x2="800" y2="240" gradientUnits="userSpaceOnUse">
            <stop stopColor="#181715" stopOpacity="0.8" />
            <stop offset="1" stopColor="#0A0A0A" stopOpacity="0.98" />
          </linearGradient>
          <linearGradient id="skyline-fade-front" x1="800" y1="90" x2="800" y2="240" gradientUnits="userSpaceOnUse">
            <stop stopColor="#121110" stopOpacity="0.95" />
            <stop offset="1" stopColor="#0A0A0A" stopOpacity="1" />
          </linearGradient>
        </defs>

        {/* Layer 1: Background Silhouette (Taller residential complexes, subtle rooftop water tanks) */}
        <g fill="url(#skyline-fade-back)" stroke="rgba(255, 255, 255, 0.035)" strokeWidth="1">
          {/* Far Left Tower */}
          <path d="M0 240V95H40V80H60V95H90V240" />
          {/* Residential block 2 */}
          <path d="M120 240V65H180V55H195V65H230V240" />
          {/* Pitched roof house cluster 1 */}
          <path d="M260 240V120L310 80L360 120V240" />
          <path d="M370 240V135L415 100L460 135V240" />
          {/* High-rise apartment tower with rooftop terrace */}
          <path d="M490 240V48H555V40H575V48H610V240" />
          {/* Duplex apartments */}
          <path d="M640 240V110L685 75L730 110V240" />
          {/* Central residential towers */}
          <path d="M760 240V60H830V240" />
          <path d="M840 240V35H920V25H940V35H970V240" />
          {/* Pitched roofs cluster 2 */}
          <path d="M1000 240V115L1050 78L1100 115V240" />
          <path d="M1120 240V85H1190V240" />
          {/* Right apartment complexes */}
          <path d="M1220 240V50H1295V240" />
          <path d="M1320 240V105L1370 65L1420 105V240" />
          <path d="M1450 240V75H1530V240" />
          <path d="M1540 240V55H1600V240" />
        </g>

        {/* Faint Warm-Amber Lit Windows in background apartments */}
        <g fill="rgba(245, 158, 11, 0.12)">
          {/* Far Left Tower windows */}
          <rect x="18" y="110" width="7" height="9" rx="1" />
          <rect x="30" y="110" width="7" height="9" rx="1" />
          <rect x="18" y="130" width="7" height="9" rx="1" />
          <rect x="70" y="110" width="7" height="9" rx="1" />
          {/* Tower 2 windows */}
          <rect x="145" y="85" width="8" height="10" rx="1" />
          <rect x="165" y="85" width="8" height="10" rx="1" />
          <rect x="145" y="105" width="8" height="10" rx="1" />
          <rect x="200" y="85" width="8" height="10" rx="1" />
          <rect x="200" y="105" width="8" height="10" rx="1" />
          {/* Tower 490 windows */}
          <rect x="515" y="70" width="8" height="11" rx="1" />
          <rect x="535" y="70" width="8" height="11" rx="1" />
          <rect x="575" y="70" width="8" height="11" rx="1" />
          <rect x="515" y="92" width="8" height="11" rx="1" />
          <rect x="575" y="92" width="8" height="11" rx="1" />
          {/* Central Highrise 840 windows */}
          <rect x="860" y="55" width="9" height="12" rx="1" />
          <rect x="880" y="55" width="9" height="12" rx="1" />
          <rect x="880" y="80" width="9" height="12" rx="1" />
          <rect x="925" y="55" width="9" height="12" rx="1" />
          <rect x="925" y="80" width="9" height="12" rx="1" />
          {/* Right Tower windows */}
          <rect x="1245" y="75" width="8" height="11" rx="1" />
          <rect x="1270" y="75" width="8" height="11" rx="1" />
          <rect x="1270" y="100" width="8" height="11" rx="1" />
          <rect x="1475" y="95" width="8" height="11" rx="1" />
        </g>

        {/* Layer 2: Foreground Residential Silhouette (Closer rooflines & apartment fronts) */}
        <g fill="url(#skyline-fade-front)" stroke="rgba(255, 255, 255, 0.05)" strokeWidth="1">
          <path d="M0 240V130L45 95L90 130H150V110H210V140L250 115L290 140H350V120H420V150L460 120L500 150H560V105H630V240" />
          <path d="M630 240V130L670 100L710 130H780V115H860V140L905 105L950 140H1020V120H1090V240" />
          <path d="M1090 240V135L1140 100L1190 135H1260V110H1330V145L1375 110L1420 145H1490V125H1600V240" />
        </g>

        {/* Faint Emerald/Mint safety & keyhole accents in foreground */}
        <g fill="rgba(52, 211, 153, 0.1)">
          <rect x="170" y="125" width="7" height="9" rx="1" />
          <rect x="375" y="135" width="7" height="9" rx="1" />
          <rect x="805" y="130" width="7" height="9" rx="1" />
          <rect x="1285" y="125" width="7" height="9" rx="1" />
        </g>
      </svg>
    </div>
  )
}
