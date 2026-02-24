"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { PencilSimple } from "@phosphor-icons/react";
import {
	getUser,
	getUserReputation,
	updateUserProfile,
	getCurrentUser,
} from "@/lib/api";
import { User, Reputation } from "@/lib/types";

interface EditModalProps {
	field: string;
	label: string;
	value: string;
	type: "text" | "textarea" | "email";
	onSave: (value: string) => void;
	onClose: () => void;
}

function EditModal({
	field,
	label,
	value,
	type,
	onSave,
	onClose,
}: EditModalProps) {
	const [editValue, setEditValue] = useState(value);
	const [loading, setLoading] = useState(false);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setLoading(true);
		try {
			await onSave(editValue);
			onClose();
		} catch (err) {
			alert("Failed to update");
		} finally {
			setLoading(false);
		}
	};

	return (
		<div
			className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
			onClick={onClose}
		>
			<div
				className="bg-white rounded-lg p-6 max-w-md w-full mx-4"
				onClick={(e) => e.stopPropagation()}
			>
				<h3 className="text-lg font-semibold mb-4">Edit {label}</h3>
				<form onSubmit={handleSubmit} className="space-y-4">
					<div className="space-y-2">
						<Label htmlFor="edit-value">{label}</Label>
						{type === "textarea" ? (
							<Textarea
								id="edit-value"
								value={editValue}
								onChange={(e) => setEditValue(e.target.value)}
								rows={5}
							/>
						) : (
							<Input
								id="edit-value"
								type={type}
								value={editValue}
								onChange={(e) => setEditValue(e.target.value)}
							/>
						)}
					</div>
					<div className="flex justify-end gap-2">
						<Button type="button" variant="outline" onClick={onClose}>
							Cancel
						</Button>
						<Button type="submit" disabled={loading}>
							{loading ? "Saving..." : "Save"}
						</Button>
					</div>
				</form>
			</div>
		</div>
	);
}

interface EditableFieldProps {
	value: string;
	canEdit: boolean;
	field: string;
	label: string;
	type?: "text" | "textarea" | "email";
	onEdit: (
		field: string,
		label: string,
		value: string,
		type: "text" | "textarea" | "email",
	) => void;
}

function EditableField({
	value,
	canEdit,
	field,
	label,
	type = "text",
	onEdit,
}: EditableFieldProps) {
	return (
		<div className="flex items-start justify-between gap-2">
			<div>{value || "—"}</div>
			{canEdit && (
				<button
					onClick={() => onEdit(field, label, value || "", type)}
					className="text-muted-foreground hover:text-foreground"
					aria-label={`Edit ${label}`}
				>
					<PencilSimple className="w-4 h-4" />
				</button>
			)}
		</div>
	);
}

export default function UserProfilePage({
	params,
}: {
	params: Promise<{ userId: string }>;
}) {
	const router = useRouter();
	const { userId: userIdParam } = use(params);
	const userId = Number.parseInt(userIdParam, 10);
	const [user, setUser] = useState<User | null>(null);
	const [reputation, setReputation] = useState<Reputation | null>(null);
	const [currentUser, setCurrentUser] = useState<User | null>(null);
	const [loading, setLoading] = useState(true);
	const [editModal, setEditModal] = useState<{
		field: string;
		label: string;
		value: string;
		type: "text" | "textarea" | "email";
	} | null>(null);

	useEffect(() => {
		async function loadData() {
			try {
				const [userData, repData, current] = await Promise.all([
					getUser(userId),
					getUserReputation(userId).catch(() => null),
					getCurrentUser(),
				]);
				setUser(userData);
				setReputation(repData);
				setCurrentUser(current);
			} catch (err) {
				console.error("Failed to load user data", err);
			} finally {
				setLoading(false);
			}
		}
		loadData();
	}, [userId]);

	const canEdit = currentUser?.id === userId;

	const handleEdit = (
		field: string,
		label: string,
		value: string,
		type: "text" | "textarea" | "email",
	) => {
		setEditModal({ field, label, value, type });
	};

	const handleSave = async (value: string) => {
		if (!user) return;
		await updateUserProfile(user.id, {
			[editModal!.field]: value || undefined,
		});
		setUser({ ...user, [editModal!.field]: value || undefined });
		router.refresh();
	};

	if (loading) {
		return <div>Loading...</div>;
	}

	if (!user) {
		return <div>User not found</div>;
	}

	return (
		<>
			<div className="flex items-start justify-between gap-3 mb-4">
				<div className="w-full">
					<div className="flex items-start justify-between gap-2">
						<div>
							<h1 className="text-2xl font-semibold mb-1 flex items-center gap-2">
								{user.name}
								{canEdit && (
									<button
										onClick={() =>
											handleEdit("name", "Name", user.name || "", "text")
										}
										className="text-muted-foreground hover:text-foreground"
										aria-label="Edit name"
									>
										<PencilSimple className="w-4 h-4" />
									</button>
								)}
							</h1>
							<div className="text-muted-foreground flex items-center gap-2">
								<EditableField
									value={user.major || "Undeclared"}
									canEdit={canEdit}
									field="major"
									label="Major"
									type="text"
									onEdit={handleEdit}
								/>
								{user.year && " · "}
								<EditableField
									value={user.year || ""}
									canEdit={canEdit}
									field="year"
									label="Year"
									type="text"
									onEdit={handleEdit}
								/>
							</div>
						</div>
						{canEdit && <Badge variant="default">You</Badge>}
					</div>

					<div className="mt-3">
						<Badge variant="secondary">Overall</Badge>
						<span className="ml-2 text-sm">
							<span className="text-muted-foreground">Contrib</span>{" "}
							<span className="font-semibold">
								{reputation?.contribution_avg || 0}
							</span>
							{" · "}
							<span className="text-muted-foreground">Comm</span>{" "}
							<span className="font-semibold">
								{reputation?.communication_avg || 0}
							</span>
							{" · "}
							<span className="text-muted-foreground">WWA</span>{" "}
							<span className="font-semibold">
								{reputation && reputation.would_work_again_ratio !== null
									? `${Math.round(reputation.would_work_again_ratio * 100)}%`
									: "—"}
							</span>
							<span className="text-muted-foreground">
								{" "}
								(n={reputation?.rating_count || 0})
							</span>
						</span>
					</div>
				</div>
			</div>

			<div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
				<div className="lg:col-span-2 space-y-4">
					<Card>
						<CardHeader className="flex flex-row items-center justify-between">
							<CardTitle className="text-sm uppercase text-muted-foreground">
								About
							</CardTitle>
							{canEdit && (
								<button
									onClick={() =>
										handleEdit("bio", "Bio", user.bio || "", "textarea")
									}
									className="text-muted-foreground hover:text-foreground"
									aria-label="Edit bio"
								>
									<PencilSimple className="w-4 h-4" />
								</button>
							)}
						</CardHeader>
						<CardContent>
							<p>{user.bio || "No bio yet."}</p>
						</CardContent>
					</Card>

					<Card>
						<CardHeader>
							<CardTitle className="text-sm uppercase text-muted-foreground">
								Contact
							</CardTitle>
						</CardHeader>
						<CardContent className="space-y-4">
							<div>
								<div className="text-sm text-muted-foreground mb-1">Email</div>
								<EditableField
									value={user.email || ""}
									canEdit={canEdit}
									field="email"
									label="Email"
									type="email"
									onEdit={handleEdit}
								/>
							</div>
							<div>
								<div className="text-sm text-muted-foreground mb-1">Phone</div>
								<EditableField
									value={user.phone || ""}
									canEdit={canEdit}
									field="phone"
									label="Phone"
									type="text"
									onEdit={handleEdit}
								/>
							</div>
							<div>
								<div className="text-sm text-muted-foreground mb-1">Link</div>
								{user.contact ? (
									<a
										href={user.contact}
										target="_blank"
										rel="noopener noreferrer"
										className="text-blue-600 hover:underline"
									>
										{user.contact}
									</a>
								) : (
									<EditableField
										value={user.contact || ""}
										canEdit={canEdit}
										field="contact"
										label="Contact link"
										type="text"
										onEdit={handleEdit}
									/>
								)}
							</div>
						</CardContent>
					</Card>
				</div>

				<div className="lg:col-span-3">
					<Card>
						<CardHeader>
							<div className="flex items-center justify-between">
								<CardTitle>Contest history</CardTitle>
								<span className="text-sm text-muted-foreground">
									Finished contests
								</span>
							</div>
						</CardHeader>
						<CardContent>
							<div className="text-muted-foreground">
								No finished contests yet.
							</div>
						</CardContent>
					</Card>
				</div>
			</div>

			{editModal && (
				<EditModal
					field={editModal.field}
					label={editModal.label}
					value={editModal.value}
					type={editModal.type}
					onSave={handleSave}
					onClose={() => setEditModal(null)}
				/>
			)}
		</>
	);
}
