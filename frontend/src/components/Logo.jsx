import './Logo.css';
import logoLexDeep from '../assets/logos/logo-lexdeep-transparent.png';
import logoLexDeepOld from '../assets/logos/logo-lexdeep.png';
import logoIcon from '../assets/logos/logo-icon.png';
import logoTextOnly from '../assets/logos/logo-text-only.svg';
import logoIntegrated from '../assets/logos/logo-integrated.svg';
import logoBadgeDark from '../assets/logos/logo-badge-dark.svg';
import logoBadgeLight from '../assets/logos/logo-badge-light.svg';

function Logo({ variant = 'default', className = '' }) {
  // Map variants to logo files
  const logoVariants = {
    'default': logoLexDeep,
    'lexdeep': logoLexDeep,
    'lexdeep-old': logoLexDeepOld,
    'text-only': logoTextOnly,
    'icon-text': logoIcon,
    'icon': logoIcon,
    'integrated': logoIntegrated,
    'badge-dark': logoBadgeDark,
    'badge-light': logoBadgeLight,
  };

  const logoSrc = logoVariants[variant] || logoLexDeep;

  return (
    <div className={`logo-container ${className}`}>
      <img 
        src={logoSrc} 
        alt="LexDeep" 
        className="logo-image"
      />
    </div>
  );
}

export default Logo;



