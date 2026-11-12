"use client";

import { useState } from "react";

import { Avatar } from "@/components/ui";

export default function EmployeeAvatar({
  employeeId,
  name,
  faceEnrolled,
  className = "size-16 text-lg",
}: {
  employeeId: string;
  name: string;
  faceEnrolled: boolean;
  className?: string;
}) {
  const [imageError, setImageError] = useState(false);

  if (faceEnrolled && !imageError) {
    return (
      <div className={`relative overflow-hidden rounded-full ring-2 ring-brand-500/20 ${className}`}>
        <img
          src={`/api/proxy/api/v1/employees/${employeeId}/avatar`}
          alt={name}
          className="h-full w-full object-cover"
          onError={() => setImageError(true)}
        />
      </div>
    );
  }

  return <Avatar name={name} className={className} />;
}

