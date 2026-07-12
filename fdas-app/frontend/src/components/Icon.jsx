import {
  Archive,
  ArrowRight,
  BarChart3,
  Bell,
  Bolt,
  Camera,
  Check,
  CheckCircle,
  Circle,
  Clock,
  Download,
  Edit,
  Eye,
  EyeOff,
  FileBarChart,
  Focus,
  GraduationCap,
  Hourglass,
  Lightbulb,
  Lock,
  LogIn,
  LogOut,
  MapPin,
  Menu,
  Plus,
  ScanFace,
  School,
  Search,
  Settings,
  Upload,
  User,
  UserPlus,
  Users,
  UserX,
  Video,
  VideoOff,
  X,
} from 'lucide-react'

const ICONS = {
  add: Plus,
  add_a_photo: Camera,
  archive: Archive,
  arrow_forward: ArrowRight,
  assessment: FileBarChart,
  bar_chart: BarChart3,
  bolt: Bolt,
  center_focus_strong: Focus,
  check: Check,
  check_circle: CheckCircle,
  close: X,
  dashboard: BarChart3,
  domain: School,
  download: Download,
  edit: Edit,
  error: Circle,
  event_available: CheckCircle,
  event_busy: UserX,
  expand_less: ArrowRight,
  expand_more: ArrowRight,
  face: ScanFace,
  group: Users,
  group_off: UserX,
  groups: Users,
  hourglass_empty: Hourglass,
  location_on: MapPin,
  lock: Lock,
  login: LogIn,
  logout: LogOut,
  manage_accounts: Users,
  menu: Menu,
  notifications: Bell,
  pending: Clock,
  pending_actions: Clock,
  person: User,
  person_add: UserPlus,
  photo_camera: Camera,
  psychology: Lightbulb,
  radio_button_unchecked: Circle,
  school: GraduationCap,
  search: Search,
  settings: Settings,
  task_alt: CheckCircle,
  trending_up: BarChart3,
  upload: Upload,
  verified: CheckCircle,
  verified_user: CheckCircle,
  videocam: Video,
  videocam_off: VideoOff,
  visibility: Eye,
  visibility_off: EyeOff,
}

export default function Icon({ name, size = 20, className = '', style, title, ...props }) {
  const LucideIcon = ICONS[name] || Circle
  const rotation = name === 'expand_less' ? '-90deg' : name === 'expand_more' ? '90deg' : undefined

  return (
    <LucideIcon
      aria-hidden={title ? undefined : true}
      aria-label={title}
      className={className}
      size={size}
      strokeWidth={2.2}
      style={{ display: 'inline-block', verticalAlign: 'middle', transform: rotation, ...style }}
      {...props}
    />
  )
}
