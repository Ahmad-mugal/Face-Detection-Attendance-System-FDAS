import { useState } from 'react'
import Icon from './Icon'

function PasswordField({ id, label, value, onChange, error }) {
  const [visible, setVisible] = useState(false)
  return (
    <label className="grid gap-1" htmlFor={id}>
      <span className="fdas-label">{label}</span>
      <div className="fdas-auth-input-wrap">
        <span className="fdas-auth-leading-icon"><Icon name="lock" size={19} /></span>
        <input
          id={id}
          required
          type={visible ? 'text' : 'password'}
          autoComplete="new-password"
          minLength="8"
          maxLength="128"
          value={value}
          onChange={event => onChange(event.target.value)}
          className="fdas-input fdas-auth-input-leading fdas-auth-input-trailing"
          aria-invalid={Boolean(error)}
        />
        <button type="button" onClick={() => setVisible(current => !current)} className="fdas-auth-trailing-action" aria-label={`${visible ? 'Hide' : 'Show'} ${label.toLowerCase()}`} title={`${visible ? 'Hide' : 'Show'} password`}>
          <Icon name={visible ? 'visibility' : 'visibility_off'} size={19} />
        </button>
      </div>
      {error && <span className="text-xs font-semibold" style={{ color: '#93000a' }}>{error}</span>}
    </label>
  )
}

export default function RecoveryPasswordFields({ form, setField, errors }) {
  return (
    <>
      <PasswordField id="newPassword" label="New Password" value={form.newPassword} onChange={value => setField('newPassword', value)} error={errors.newPassword} />
      <PasswordField id="confirmPassword" label="Confirm New Password" value={form.confirmPassword} onChange={value => setField('confirmPassword', value)} error={errors.confirmPassword} />
    </>
  )
}
