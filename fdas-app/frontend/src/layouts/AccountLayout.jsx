import { useAuth } from '../context/useAuth'
import AdminLayout from './AdminLayout'
import UserLayout from './UserLayout'

export default function AccountLayout() {
  const { isAdmin } = useAuth()
  return isAdmin() ? <AdminLayout /> : <UserLayout />
}
