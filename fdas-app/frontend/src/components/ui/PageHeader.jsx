export default function PageHeader({ eyebrow, title, description, actions, children, className = '' }) {
  return (
    <header className={`fdas-page-header ${className}`.trim()}>
      <div className="fdas-page-heading">
        {eyebrow && <p className="fdas-eyebrow">{eyebrow}</p>}
        <h1 className="fdas-page-title">{title}</h1>
        {description && <p className="fdas-page-description">{description}</p>}
        {children}
      </div>
      {actions && <div className="fdas-page-actions">{actions}</div>}
    </header>
  )
}
