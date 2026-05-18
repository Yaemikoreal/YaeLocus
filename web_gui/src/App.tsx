import { Routes, Route } from 'react-router-dom'
import Layout from './components/layout/Layout'
import GeocodePage from './pages/GeocodePage'
import BatchPage from './pages/BatchPage'
import ReversePage from './pages/ReversePage'
import ConvertPage from './pages/ConvertPage'
import MapPage from './pages/MapPage'
import AIPage from './pages/AIPage'
import RoutePage from './pages/RoutePage'
import OptimizePage from './pages/OptimizePage'
import HistoryPage from './pages/HistoryPage'
import FilesPage from './pages/FilesPage'
import CachePage from './pages/CachePage'
import ConfigPage from './pages/ConfigPage'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<GeocodePage />} />
        <Route path="/batch" element={<BatchPage />} />
        <Route path="/reverse" element={<ReversePage />} />
        <Route path="/convert" element={<ConvertPage />} />
        <Route path="/map" element={<MapPage />} />
        <Route path="/ai" element={<AIPage />} />
        <Route path="/route" element={<RoutePage />} />
        <Route path="/optimize" element={<OptimizePage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/files" element={<FilesPage />} />
        <Route path="/cache" element={<CachePage />} />
        <Route path="/config" element={<ConfigPage />} />
      </Routes>
    </Layout>
  )
}
