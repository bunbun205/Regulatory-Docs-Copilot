import { lazy, Suspense, useCallback, useEffect, useState } from 'react';
import { Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { BookOpen, ChevronRight, Files, KeyRound, Menu, MessageSquare, Moon, Search, Settings2, ShieldCheck, Sparkles, Sun } from 'lucide-react';
import { useSettings } from './app/context';
import { Button, Card, Drawer, IconButton, Skeleton } from './components/ui';
import styles from './app/AppShell.module.css';

const Ask = lazy(() => import('./views/AskView'));
const SearchView = lazy(() => import('./views/SearchView'));
const Agent = lazy(() => import('./views/AgentView'));
const GapCheck = lazy(() => import('./views/GapCheckView'));
const Documents = lazy(() => import('./views/DocumentsView'));
const Settings = lazy(() => import('./views/SettingsView'));

const navigation = [
  { path: '/ask', label: 'Ask documents', short: 'Ask', icon: MessageSquare, description: 'Find answers in your loaded documents, then review the sources.' },
  { path: '/search', label: 'Search library', short: 'Search', icon: Search, description: 'Find relevant passages across your document library.' },
  { path: '/agent', label: 'Research agent', short: 'Agent', icon: Sparkles, description: 'Explore a question with a bounded research assistant.' },
  { path: '/gap-check', label: 'Gap check', short: 'Gap Check', icon: ShieldCheck, description: 'Compare an SOP with the regulations in your library.' },
  { path: '/documents', label: 'Documents', short: 'Documents', icon: Files, description: 'Manage the documents that inform your answers and reviews.' },
  { path: '/settings', label: 'Settings', short: 'Settings', icon: Settings2, description: 'Connect your API, check access and make this workspace yours.' },
];

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  return <nav aria-label="Main navigation" className={styles.navigation}>{navigation.map(item => <NavLink key={item.path} to={item.path} onClick={onNavigate} className={({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ''}`}><item.icon size={18} strokeWidth={1.7} aria-hidden="true" /><span>{item.label}</span>{item.path === '/gap-check' && <span className={styles.navNote}>SOP</span>}</NavLink>)}</nav>;
}

export default function App() {
  const { key, identity, unauthorized, readiness, preferences, updatePreferences } = useSettings();
  const [menuOpen, setMenuOpen] = useState(false);
  const [systemDark, setSystemDark] = useState(() => matchMedia('(prefers-color-scheme: dark)').matches);
  const closeMenu = useCallback(() => setMenuOpen(false), []);
  const location = useLocation();
  const navigate = useNavigate();
  const page = navigation.find(item => location.pathname.startsWith(item.path)) ?? navigation[0];
  const online = !readiness.error && readiness.data?.status === 'ok';
  const scope = identity?.scopes.includes('write') ? 'Read & write' : 'Read only';
  const connection = identity ? identity.name : key ? 'Validate key' : 'Connect API';
  useEffect(() => {
    const media = matchMedia('(prefers-color-scheme: dark)');
    const changed = () => setSystemDark(media.matches);
    media.addEventListener('change', changed);
    return () => media.removeEventListener('change', changed);
  }, []);
  useEffect(() => { if (location.pathname === '/') navigate('/ask', { replace: true }); }, [location.pathname, navigate]);
  useEffect(() => { if (unauthorized && location.pathname !== '/settings') navigate('/settings', { replace: true }); }, [unauthorized, location.pathname, navigate]);
  useEffect(() => { document.title = `${page.short} · Docs Copilot`; }, [page.short]);
  const dark = preferences.theme === 'dark' || (preferences.theme === 'system' && systemDark);
  const toggleTheme = () => updatePreferences({ theme: dark ? 'light' : 'dark' });

  return <div className={styles.shell}>
    <a className={styles.skip} href="#workspace-content">Skip to content</a>
    <aside className={styles.rail}>
      <Link to="/ask" className={styles.brand}><span className={styles.brandIcon}><BookOpen size={22} strokeWidth={1.6} aria-hidden="true" /></span><span>Docs Copilot<small>REGULATORY WORKBENCH</small></span></Link>
      <div className={styles.railLabel}>WORKSPACE</div><Navigation />
      <div className={styles.railFoot}><ShieldCheck size={16} aria-hidden="true" /><span>Decision support.<br />Always review the sources.</span></div>
    </aside>
    <div className={styles.workspace}>
      <header className={styles.topbar}>
        <div className={styles.mobileMenu}><IconButton label="Open navigation" onClick={() => setMenuOpen(true)}><Menu size={20} /></IconButton><Link to="/ask">Copilot</Link></div>
        <div className={styles.breadcrumb}><span>Workspace</span><ChevronRight size={14} aria-hidden="true" /><span>{page.short}</span></div>
        <div className={styles.headerActions}>
          <Link to="/settings" className={styles.connection} title={`${online ? 'API online' : 'API not ready'} · ${connection}${identity ? ` · ${scope}` : ''}`} aria-label={`Settings: ${online ? 'API online' : 'API not ready'}, ${connection}${identity ? `, ${scope}` : ''}`}><span className={`${styles.dot} ${online ? styles.online : ''}`} /><KeyRound size={14} aria-hidden="true" /><span className={styles.keyName}>{connection}</span>{identity && <span className={styles.scope}>{scope}</span>}</Link>
          <IconButton label={dark ? 'Switch to light theme' : 'Switch to dark theme'} onClick={toggleTheme}>{dark ? <Sun size={19} /> : <Moon size={19} />}</IconButton>
        </div>
      </header>
      <main id="workspace-content" className={styles.content} tabIndex={-1}>
        <div className={styles.pageHeader}><p className={styles.eyebrow}>{page.path === '/settings' ? 'YOUR WORKSPACE' : 'DOCUMENT WORKBENCH'}</p><h1>{page.path === '/ask' ? 'Ask your documents' : page.label}</h1><p>{page.description}</p></div>
        <Suspense fallback={<Card><Skeleton lines={5} /></Card>}>
          {!key && page.path !== '/settings' ? <Card><div className={styles.connectPrompt}><KeyRound size={26} strokeWidth={1.5} /><h2>Make a connection first</h2><p>Add and validate an API key in Settings to start working with your documents.</p><Link to="/settings" className={styles.linkButton}>Open Settings <ChevronRight size={16} /></Link></div></Card> :
            <div className={page.path === '/settings' ? '' : styles.legacy} key={page.path === '/settings' ? 'settings' : `${preferences.baseUrl}:${key}`}><Routes>
              <Route path="/" element={<Navigate to="/ask" replace />} />
              <Route path="/ask" element={<Ask />} /><Route path="/search" element={<SearchView />} />
              <Route path="/agent" element={<Agent />} /><Route path="/gap-check" element={<GapCheck />} />
              <Route path="/gap-check/:jobId" element={<GapCheck />} /><Route path="/documents" element={<Documents />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="*" element={<Card><h2>Page not found</h2><p>Choose a view from the navigation to continue.</p><Button onClick={() => navigate('/ask')}>Go to Ask</Button></Card>} />
            </Routes></div>}
        </Suspense>
        <footer className={styles.pageFoot}>Built around your documents. <span>Evidence first, decisions with you.</span></footer>
      </main>
    </div>
    <Drawer open={menuOpen} title="Your workspace" onClose={closeMenu}><Navigation onNavigate={closeMenu} /></Drawer>
  </div>;
}
