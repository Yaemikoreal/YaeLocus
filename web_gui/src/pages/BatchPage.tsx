import BatchGeocode from '../components/geocode/BatchGeocode'
import { useQuery } from '@tanstack/react-query'
import { fetchConfig } from '../lib/api'
import { AlertTriangle, ServerOff } from 'lucide-react'

export default function BatchPage() {
  const { data: config, isError } = useQuery({
    queryKey: ['config'],
    queryFn: ({ signal }) => fetchConfig(signal),
    retry: 1,
  })

  const hasApiKey = (config?.apis?.length ?? 0) > 0

  return (
    <div className="page">
      {isError && (
        <div className="alert alert-error">
          <ServerOff size={16} />
          无法连接到 API 服务器，请确认已启动 yaelocus serve
        </div>
      )}
      {!isError && !hasApiKey && (
        <div className="alert alert-warning">
          <AlertTriangle size={16} />
          尚未配置 API 密钥，请先前往
          <a href="/config" style={{ color: '#ff9d4d', fontWeight: 600, marginLeft: 4 }}>
            配置页面
          </a>
          设置后再使用地理编码功能
        </div>
      )}
      <BatchGeocode disabled={!hasApiKey} />
    </div>
  )
}
