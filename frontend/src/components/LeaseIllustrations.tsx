/**
 * LeaseLensLogo: Custom geometric house roofline framing a folded lease agreement with a keyhole emblem.
 */
export function LeaseLensLogo({ size = 30, className }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="LeaseLens Logo"
    >
      <defs>
        <linearGradient id="ll-roof-grad" x1="6" y1="4" x2="34" y2="20" gradientUnits="userSpaceOnUse">
          <stop stopColor="#F59E0B" />
          <stop offset="1" stopColor="#34D399" />
        </linearGradient>
        <linearGradient id="ll-page-grad" x1="12" y1="12" x2="28" y2="34" gradientUnits="userSpaceOnUse">
          <stop stopColor="#2A2725" />
          <stop offset="1" stopColor="#141312" />
        </linearGradient>
      </defs>

      {/* House roofline outer gable */}
      <path
        d="M5 19L20 6L35 19"
        stroke="url(#ll-roof-grad)"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Chimney / structural accent */}
      <path
        d="M28 12.5V8.5H31V15"
        stroke="#F59E0B"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.85"
      />

      {/* Folded Lease Agreement Body */}
      <path
        d="M12 16H23L28 21V33C28 34.1 27.1 35 26 35H12C10.9 35 10 34.1 10 33V18C10 16.9 10.9 16 12 16Z"
        fill="url(#ll-page-grad)"
        stroke="#ECEAE6"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />

      {/* Folded page corner */}
      <path
        d="M23 16V21H28"
        stroke="#ECEAE6"
        strokeWidth="1.5"
        strokeLinejoin="round"
        fill="#332F2C"
      />

      {/* Document clause lines */}
      <line x1="14" y1="21" x2="20" y2="21" stroke="#8E8B86" strokeWidth="1.3" strokeLinecap="round" />
      <line x1="14" y1="25" x2="17" y2="25" stroke="#8E8B86" strokeWidth="1.3" strokeLinecap="round" />

      {/* Central keyhole badge: protection & tenancy security */}
      <circle cx="21" cy="28.5" r="3" fill="#34D399" fillOpacity="0.2" stroke="#34D399" strokeWidth="1.4" />
      <path d="M20.2 29L19.5 32H22.5L21.8 29" stroke="#34D399" strokeWidth="1.2" strokeLinejoin="round" />
    </svg>
  )
}

/**
 * EmptyLeaseIllustration: Architectural line-art of apartment buildings, signed agreement, and house key.
 */
export function EmptyLeaseIllustration({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 340 180"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className || 'empty-lease-illustration'}
      style={{ width: '100%', maxWidth: 320, height: 'auto', margin: '0 auto 16px' }}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="empty-bldg-fade" x1="170" y1="10" x2="170" y2="170" gradientUnits="userSpaceOnUse">
          <stop stopColor="#ECEAE6" stopOpacity="0.25" />
          <stop offset="1" stopColor="#ECEAE6" stopOpacity="0.03" />
        </linearGradient>
        <radialGradient id="empty-glow" cx="170" cy="90" r="120" gradientUnits="userSpaceOnUse">
          <stop stopColor="#34D399" stopOpacity="0.12" />
          <stop offset="0.6" stopColor="#F59E0B" stopOpacity="0.05" />
          <stop offset="1" stopColor="transparent" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Ambient background glow */}
      <rect x="20" y="10" width="300" height="160" rx="20" fill="url(#empty-glow)" />

      {/* Background Apartment Skyline (Minimalist architectural line work) */}
      <g stroke="#ECEAE6" strokeOpacity="0.3" strokeWidth="1.2" strokeLinecap="round">
        {/* Left tower */}
        <path d="M45 145V60L75 42V145" />
        <line x1="55" y1="72" x2="65" y2="72" />
        <line x1="55" y1="88" x2="65" y2="88" />
        <line x1="55" y1="104" x2="65" y2="104" />
        <line x1="55" y1="120" x2="65" y2="120" />

        {/* Center residential block */}
        <path d="M75 145V75H125V145" />
        <rect x="87" y="86" width="10" height="12" rx="1.5" strokeOpacity="0.4" />
        <rect x="103" y="86" width="10" height="12" rx="1.5" strokeOpacity="0.4" />
        <rect x="87" y="106" width="10" height="12" rx="1.5" strokeOpacity="0.4" />
        <rect x="103" y="106" width="10" height="12" rx="1.5" strokeOpacity="0.4" />

        {/* Right townhouses silhouette */}
        <path d="M215 145V90L245 70L275 90V145" />
        <path d="M275 145V80L295 66V145" />
        <line x1="235" y1="102" x2="255" y2="102" />
        <line x1="235" y1="118" x2="255" y2="118" />
      </g>

      {/* Ground horizon line */}
      <line x1="30" y1="145" x2="310" y2="145" stroke="#ECEAE6" strokeOpacity="0.2" strokeWidth="1.2" strokeDasharray="3 3" />

      {/* Foreground Signed Rental Lease Agreement Document */}
      <g filter="drop-shadow(0 12px 24px rgba(0,0,0,0.6))">
        <path
          d="M135 32H188L207 51V140C207 143.3 204.3 146 201 146H135C131.7 146 129 143.3 129 140V38C129 34.7 131.7 32 135 32Z"
          fill="#1C1B1A"
          stroke="#ECEAE6"
          strokeWidth="1.6"
        />
        {/* Document Folded Corner */}
        <path d="M188 32V51H207" fill="#292725" stroke="#ECEAE6" strokeWidth="1.4" />

        {/* Header bar on lease */}
        <rect x="141" y="44" width="38" height="4" rx="2" fill="#F59E0B" fillOpacity="0.85" />

        {/* Clause lines */}
        <line x1="141" y1="58" x2="195" y2="58" stroke="#ECEAE6" strokeOpacity="0.5" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="141" y1="68" x2="190" y2="68" stroke="#ECEAE6" strokeOpacity="0.5" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="141" y1="78" x2="182" y2="78" stroke="#ECEAE6" strokeOpacity="0.5" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="141" y1="88" x2="195" y2="88" stroke="#ECEAE6" strokeOpacity="0.5" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="141" y1="98" x2="175" y2="98" stroke="#ECEAE6" strokeOpacity="0.5" strokeWidth="1.5" strokeLinecap="round" />

        {/* Tenant signature & stamp */}
        <path d="M141 122Q149 114 157 122T173 120" stroke="#34D399" strokeWidth="1.6" strokeLinecap="round" fill="none" />
        <circle cx="188" cy="122" r="9" fill="#34D399" fillOpacity="0.15" stroke="#34D399" strokeWidth="1.4" />
        {/* Checkmark in seal */}
        <path d="M184 122L187 125L193 118" stroke="#34D399" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </g>

      {/* Solid Brass Tenant Key floating beside lease */}
      <g transform="translate(198, 76) rotate(-28)">
        {/* Key Bow */}
        <circle cx="20" cy="20" r="11" fill="#1C1B1A" stroke="#F59E0B" strokeWidth="2.2" />
        <circle cx="20" cy="20" r="5" stroke="#F59E0B" strokeWidth="1.6" fill="#141312" />
        {/* Key Blade */}
        <path d="M31 20H60V25H55V21H48V26H44V20" stroke="#F59E0B" strokeWidth="2" strokeLinejoin="round" fill="#F59E0B" fillOpacity="0.15" />
      </g>
    </svg>
  )
}

/**
 * IsometricLeaseVaultSvg: Stacked rental agreements with privacy lock and house key.
 */
export function IsometricLeaseVaultSvg({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 280 190"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className || 'feature-glyph'}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="vault-grad" x1="140" y1="20" x2="140" y2="170" gradientUnits="userSpaceOnUse">
          <stop stopColor="#34D399" stopOpacity="0.2" />
          <stop offset="1" stopColor="#10B981" stopOpacity="0.02" />
        </linearGradient>
      </defs>

      {/* Isometric plane base glow */}
      <path d="M140 24L240 78L140 134L40 78Z" fill="url(#vault-grad)" stroke="#34D399" strokeWidth="1.2" strokeOpacity="0.4" />

      {/* Lower Agreement Page (isometric) */}
      <path d="M60 84L140 128L220 84L140 40Z" fill="#171615" stroke="#ECEAE6" strokeOpacity="0.4" strokeWidth="1.4" />

      {/* Middle Agreement Page */}
      <path d="M60 76L140 120L220 76L140 32Z" fill="#1E1D1B" stroke="#ECEAE6" strokeOpacity="0.6" strokeWidth="1.4" />

      {/* Top Agreement Page */}
      <path d="M60 68L140 112L220 68L140 24Z" fill="#252422" stroke="#ECEAE6" strokeWidth="1.6" />

      {/* Isometric text lines on top lease */}
      <line x1="88" y1="62" x2="132" y2="86" stroke="#ECEAE6" strokeOpacity="0.7" strokeWidth="1.6" strokeLinecap="round" />
      <line x1="88" y1="70" x2="124" y2="90" stroke="#ECEAE6" strokeOpacity="0.5" strokeWidth="1.4" strokeLinecap="round" />
      <line x1="88" y1="78" x2="116" y2="94" stroke="#ECEAE6" strokeOpacity="0.5" strokeWidth="1.4" strokeLinecap="round" />
      <line x1="148" y1="56" x2="192" y2="80" stroke="#34D399" strokeOpacity="0.8" strokeWidth="1.6" strokeLinecap="round" />

      {/* Security Vault Lock & Shield on top of lease */}
      <g transform="translate(140, 78)">
        {/* Shackle */}
        <path d="M-10 -4V-14C-10 -20 -4 -25 0 -25C4 -25 10 -20 10 -14V-4" stroke="#F59E0B" strokeWidth="2.4" strokeLinecap="round" fill="none" />
        {/* Lock Body */}
        <rect x="-18" y="-4" width="36" height="30" rx="6" fill="#1A1918" stroke="#F59E0B" strokeWidth="1.8" />
        {/* Keyhole */}
        <circle cx="0" cy="8" r="3.5" fill="#F59E0B" />
        <path d="M-1.5 10L-2.5 17H2.5L1.5 10" fill="#F59E0B" />
      </g>

      {/* House Key lying at the edge of the vault */}
      <g transform="translate(195, 110) rotate(-15)">
        <circle cx="0" cy="0" r="9" stroke="#34D399" strokeWidth="1.8" fill="#141312" />
        <circle cx="0" cy="0" r="4" stroke="#34D399" strokeWidth="1.2" />
        <path d="M9 0H32V5H28V1H22V6H18V0" stroke="#34D399" strokeWidth="1.8" fill="#34D399" fillOpacity="0.2" />
      </g>
    </svg>
  )
}

/**
 * IsometricLawScaleSvg: Minimalist balance scale weighing lease clause vs. statutory protection.
 */
export function IsometricLawScaleSvg({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 280 190"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className || 'feature-glyph'}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="law-grad" x1="140" y1="20" x2="140" y2="170" gradientUnits="userSpaceOnUse">
          <stop stopColor="#F59E0B" stopOpacity="0.2" />
          <stop offset="1" stopColor="#34D399" stopOpacity="0.02" />
        </linearGradient>
      </defs>

      {/* Base platform */}
      <path d="M140 140L200 162L140 184L80 162Z" fill="url(#law-grad)" stroke="#ECEAE6" strokeOpacity="0.3" strokeWidth="1.2" />

      {/* Main central pedestal */}
      <line x1="140" y1="60" x2="140" y2="162" stroke="#ECEAE6" strokeWidth="2.8" strokeLinecap="round" />
      <circle cx="140" cy="55" r="5" fill="#F59E0B" stroke="#ECEAE6" strokeWidth="1.5" />

      {/* Balance beam tilted slightly (statutory law outweighs unfair clause) */}
      <line x1="68" y1="74" x2="212" y2="46" stroke="#ECEAE6" strokeWidth="2.4" strokeLinecap="round" />

      {/* Left scale pan: Disputed Lease Clause card */}
      <line x1="68" y1="74" x2="52" y2="108" stroke="#ECEAE6" strokeOpacity="0.5" strokeWidth="1.2" />
      <line x1="68" y1="74" x2="84" y2="108" stroke="#ECEAE6" strokeOpacity="0.5" strokeWidth="1.2" />
      <g transform="translate(68, 118)">
        {/* Pan */}
        <ellipse cx="0" cy="0" rx="26" ry="10" fill="#1E1D1B" stroke="#ECEAE6" strokeWidth="1.4" />
        {/* Clause card sitting on pan */}
        <path d="M-14 -24L10 -30L14 -10L-10 -4Z" fill="#2A2220" stroke="#EF4444" strokeWidth="1.4" />
        <line x1="-8" y1="-20" x2="4" y2="-23" stroke="#EF4444" strokeWidth="1.2" />
        <line x1="-7" y1="-14" x2="3" y2="-17" stroke="#EF4444" strokeWidth="1.2" />
      </g>

      {/* Right scale pan: Statutory Protection Shield (weighs heavier/firm) */}
      <line x1="212" y1="46" x2="196" y2="78" stroke="#ECEAE6" strokeOpacity="0.5" strokeWidth="1.2" />
      <line x1="212" y1="46" x2="228" y2="78" stroke="#ECEAE6" strokeOpacity="0.5" strokeWidth="1.2" />
      <g transform="translate(212, 88)">
        {/* Pan */}
        <ellipse cx="0" cy="0" rx="26" ry="10" fill="#1E1D1B" stroke="#34D399" strokeWidth="1.5" />
        {/* Tenant Rights Shield sitting on pan */}
        <path
          d="M0 -28L13 -22V-10C13 0 0 8 0 8C0 8 -13 0 -13 -10V-22L0 -28Z"
          fill="#1A261E"
          stroke="#34D399"
          strokeWidth="1.6"
        />
        <path d="M-4 -12L-1 -9L5 -16" stroke="#34D399" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </g>
    </svg>
  )
}

/**
 * IsometricRefundShieldSvg: Rupee (₹) coin and recovery shield rising from legal notice.
 */
export function IsometricRefundShieldSvg({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 280 190"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className || 'feature-glyph'}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="shield-grad" x1="140" y1="30" x2="140" y2="160" gradientUnits="userSpaceOnUse">
          <stop stopColor="#34D399" stopOpacity="0.25" />
          <stop offset="1" stopColor="#F59E0B" stopOpacity="0.04" />
        </linearGradient>
      </defs>

      {/* Isometric floor plane */}
      <path d="M140 32L240 84L140 138L40 84Z" fill="url(#shield-grad)" stroke="#34D399" strokeOpacity="0.3" strokeWidth="1.2" />

      {/* Formal Demand Notice document lying isometrically */}
      <path d="M80 82L150 120L210 88L140 50Z" fill="#1C1B1A" stroke="#ECEAE6" strokeWidth="1.5" />
      <line x1="102" y1="78" x2="135" y2="96" stroke="#ECEAE6" strokeOpacity="0.6" strokeWidth="1.4" strokeLinecap="round" />
      <line x1="102" y1="86" x2="128" y2="100" stroke="#ECEAE6" strokeOpacity="0.4" strokeWidth="1.4" strokeLinecap="round" />

      {/* Isometric 3D Rupee Coin rising upwards */}
      <g transform="translate(140, 68)">
        {/* Coin extrusion / edge */}
        <path
          d="M-30 0C-30 11 -13 20 7 20C27 20 44 11 44 0V8C44 19 27 28 7 28C-13 28 -30 19 -30 8V0Z"
          fill="#B45309"
        />
        {/* Coin Face */}
        <ellipse cx="7" cy="0" rx="37" ry="20" fill="#F59E0B" stroke="#FDE68A" strokeWidth="1.6" />
        <ellipse cx="7" cy="0" rx="31" ry="16" fill="#D97706" stroke="#F59E0B" strokeWidth="1.2" />

        {/* Rupee Symbol (₹) on coin */}
        <g stroke="#FFFBEB" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" fill="none">
          <path d="M-1 -8H15" />
          <path d="M-1 -3H15" />
          <path d="M4 -8V8" />
          <path d="M4 -3C12 -3 12 5 4 5H2L13 11" />
        </g>
      </g>

      {/* Radiating Protection Rays */}
      <line x1="90" y1="36" x2="74" y2="24" stroke="#34D399" strokeWidth="1.5" strokeLinecap="round" opacity="0.7" />
      <line x1="147" y1="20" x2="147" y2="6" stroke="#34D399" strokeWidth="1.5" strokeLinecap="round" opacity="0.8" />
      <line x1="204" y1="36" x2="220" y2="24" stroke="#34D399" strokeWidth="1.5" strokeLinecap="round" opacity="0.7" />
    </svg>
  )
}
