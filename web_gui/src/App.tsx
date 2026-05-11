import { Routes, Route } from 'react-router-dom'
import Layout from './components/layout/Layout'
import GeocodePage from './pages/GeocodePage'
import MapPage from './pages/MapPage'
import AIPage from './pages/AIPage'
import ConfigPage from './pages/ConfigPage'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<GeocodePage />} />
        <Route path="/map" element={<MapPage />} />
        <Route path="/ai" element={<AIPage />} />
        <Route path="/config" element={<ConfigPage />} />
      </Routes>
    </Layout>
  )
}
