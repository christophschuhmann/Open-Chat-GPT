import {
  Avatar,
  AvatarProps,
  Badge,
  Box,
  Flex,
  HStack,
  Menu,
  MenuButton,
  MenuDivider,
  MenuGroup,
  MenuItem,
  MenuList,
  SimpleGrid,
  Tooltip,
  useBreakpointValue,
  useColorModeValue,
  useDisclosure,
  useToast,
} from "@chakra-ui/react";
import { boolean } from "boolean";
import {
  ClipboardList,
  Copy,
  Flag,
  Link,
  MessageSquare,
  MoreHorizontal,
  Shield,
  Slash,
  Trash,
  User,
} from "lucide-react";
import { useRouter } from "next/router";
import { useTranslation } from "next-i18next";
import { useCallback, useEffect, useMemo, useState } from "react";
import { LabelMessagePopup } from "src/components/Messages/LabelPopup";
import { MessageEmojiButton } from "src/components/Messages/MessageEmojiButton";
import { ReportPopup } from "src/components/Messages/ReportPopup";
import { useHasAnyRole } from "src/hooks/auth/useHasAnyRole";
import { del, post, put } from "src/lib/api";
import { ROUTES } from "src/lib/routes";
import { colors } from "src/styles/Theme/colors";
import { Message, MessageEmojis } from "src/types/Conversation";
import { emojiIcons, isKnownEmoji } from "src/types/Emoji";
import { mutate } from "swr";
import useSWRMutation from "swr/mutation";

interface MessageTableEntryProps {
  message: Message;
  enabled?: boolean;
  highlight?: boolean;
  avartarPosition?: "middle" | "top";
  avartarProps?: AvatarProps;
  hightlightColor?: [string, string];
}

export function MessageTableEntry({
  message,
  enabled,
  highlight,
  avartarPosition = "middle",
  avartarProps,
  hightlightColor,
}: MessageTableEntryProps) {
  const router = useRouter();
  const [emojiState, setEmojis] = useState<MessageEmojis>({ emojis: {}, user_emojis: [] });
  useEffect(() => {
    const emojis = { ...message.emojis };
    emojis["+1"] = emojis["+1"] || 0;
    emojis["-1"] = emojis["-1"] || 0;
    setEmojis({
      emojis: emojis,
      user_emojis: message?.user_emojis || [],
    });
  }, [message.emojis, message.user_emojis]);

  const goToMessage = useCallback(
    () => enabled && router.push(`/messages/${message.id}`),
    [enabled, router, message.id]
  );
  const { isOpen: reportPopupOpen, onOpen: showReportPopup, onClose: closeReportPopup } = useDisclosure();
  const { isOpen: labelPopupOpen, onOpen: showLabelPopup, onClose: closeLabelPopup } = useDisclosure();

  const bg = useColorModeValue("#DFE8F1", "#42536B");

  const borderColor = useColorModeValue("blackAlpha.200", "whiteAlpha.200");

  const inlineAvatar = useBreakpointValue({ base: true, md: false });

  const avatar = useMemo(
    () => (
      <Avatar
        borderColor={borderColor}
        size={inlineAvatar ? "xs" : "sm"}
        mr={inlineAvatar ? 2 : 0}
        name={`${boolean(message.is_assistant) ? "Assistant" : "User"}`}
        src={`${boolean(message.is_assistant) ? "/images/logos/logo.png" : "/images/temp-avatars/av1.jpg"}`}
        {...avartarProps}
      />
    ),
    [avartarProps, borderColor, inlineAvatar, message.is_assistant]
  );
  const internalHighlightColor = useColorModeValue(...(hightlightColor || [colors.light.active, colors.dark.active]));

  const { trigger: sendEmojiChange } = useSWRMutation(`/api/messages/${message.id}/emoji`, post, {
    onSuccess: (data) => {
      data.emojis["+1"] = data.emojis["+1"] || 0;
      data.emojis["-1"] = data.emojis["-1"] || 0;
      setEmojis(data);
    },
  });
  const react = (emoji: string, state: boolean) => {
    sendEmojiChange({ op: state ? "add" : "remove", emoji });
  };

  const isAdminOrMod = useHasAnyRole(["admin", "moderator"]);
  const { t } = useTranslation(["message"]);

  return (
    <HStack
      w={["full", "full", "full", "fit-content"]}
      gap={0.5}
      alignItems={avartarPosition === "top" ? "start" : "center"}
    >
      {!inlineAvatar && avatar}
      <Box
        width={["full", "full", "full", "fit-content"]}
        maxWidth={["full", "full", "full", "2xl"]}
        p={[3, 4]}
        borderRadius="18px"
        bg={bg}
        outline={highlight ? "2px solid black" : undefined}
        outlineColor={internalHighlightColor}
        onClick={goToMessage}
        whiteSpace="pre-wrap"
        cursor={enabled ? "pointer" : undefined}
        style={{ position: "relative" }}
      >
        {inlineAvatar && avatar}
        {message.text}
        <HStack
          style={{ float: "right", position: "relative", right: "-0.3em", bottom: "-0em", marginLeft: "1em" }}
          onClick={(e) => e.stopPropagation()}
        >
          {Object.entries(emojiState.emojis)
            .filter(([emoji]) => isKnownEmoji(emoji))
            .sort(([emoji]) => -emoji)
            .map(([emoji, count]) => {
              return (
                <MessageEmojiButton
                  key={emoji}
                  emoji={{ name: emoji, count }}
                  checked={emojiState.user_emojis.includes(emoji)}
                  userReacted={emojiState.user_emojis.length > 0}
                  userIsAuthor={!!message.user_is_author}
                  onClick={() => react(emoji, !emojiState.user_emojis.includes(emoji))}
                />
              );
            })}
          <MessageActions
            react={react}
            userEmoji={emojiState.user_emojis}
            onLabel={showLabelPopup}
            onReport={showReportPopup}
            message={message}
          />
          <LabelMessagePopup message={message} show={labelPopupOpen} onClose={closeLabelPopup} />
          <ReportPopup messageId={message.id} show={reportPopupOpen} onClose={closeReportPopup} />
        </HStack>
        <Flex position="absolute" gap="2" top="-2.5" right="5">
          {message.user_is_author && (
            <Tooltip label={t("message_author_explain")} placement="top">
              <Badge size="sm" colorScheme="green" textTransform="capitalize">
                {t("message_author")}
              </Badge>
            </Tooltip>
          )}
          {message.deleted && isAdminOrMod && (
            <Badge colorScheme="red" textTransform="capitalize">
              Deleted
            </Badge>
          )}
        </Flex>
      </Box>
    </HStack>
  );
}

const EmojiMenuItem = ({
  emoji,
  checked,
  react,
}: {
  emoji: string;
  checked?: boolean;
  react: (emoji: string, state: boolean) => void;
}) => {
  const activeColor = useColorModeValue(colors.light.active, colors.dark.active);
  // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
  const EmojiIcon = emojiIcons.get(emoji)!;
  return (
    <MenuItem onClick={() => react(emoji, !checked)} justifyContent="center" color={checked ? activeColor : undefined}>
      <EmojiIcon />
    </MenuItem>
  );
};

const CHAR_COUNT = 10;

const MessageActions = ({
  react,
  userEmoji,
  onLabel,
  onReport,
  message,
}: {
  react: (emoji: string, state: boolean) => void;
  userEmoji: string[];
  onLabel: () => void;
  onReport: () => void;
  message: Message;
}) => {
  const toast = useToast();
  const { t } = useTranslation(["message", "common"]);
  const { id } = message;
  const { trigger: deleteMessage } = useSWRMutation(`/api/admin/delete_message/${id}`, del);

  const { trigger: stopTree } = useSWRMutation(`/api/admin/stop_tree/${id}`, put, {
    onSuccess: () => {
      const displayId = id.slice(0, CHAR_COUNT) + "..." + id.slice(-CHAR_COUNT);
      toast({
        title: t("common:success"),
        description: t("tree_stopped", { id: displayId }),
        status: "success",
        duration: 5000,
        isClosable: true,
      });
    },
  });

  const handleDelete = async () => {
    await deleteMessage();
    mutate((key) => typeof key === "string" && key.startsWith("/api/messages"), undefined, { revalidate: true });
  };

  const handleStop = () => {
    stopTree();
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    const displayId = text.slice(0, CHAR_COUNT) + "..." + text.slice(-CHAR_COUNT);

    toast({
      title: t("common:copied"),
      description: displayId,
      status: "info",
      duration: 5000,
      isClosable: true,
    });
  };

  const isAdminOrMod = useHasAnyRole(["admin", "moderator"]);

  return (
    <Menu>
      <MenuButton>
        <MoreHorizontal />
      </MenuButton>
      <MenuList>
        <MenuGroup title={t("reactions")}>
          <SimpleGrid columns={4}>
            {["+1", "-1"].map((emoji) => (
              <EmojiMenuItem key={emoji} emoji={emoji} checked={userEmoji?.includes(emoji)} react={react} />
            ))}
          </SimpleGrid>
        </MenuGroup>
        <MenuDivider />
        <MenuItem onClick={onLabel} icon={<ClipboardList />}>
          {t("label_action")}
        </MenuItem>
        <MenuItem onClick={onReport} icon={<Flag />}>
          {t("report_action")}
        </MenuItem>
        <MenuDivider />
        <MenuItem as="a" href={`/messages/${id}`} target="_blank" icon={<MessageSquare />}>
          {t("open_new_tab_action")}
        </MenuItem>

        <MenuItem
          onClick={() => handleCopy(`${window.location.protocol}//${window.location.host}/messages/${id}`)}
          icon={<Link />}
        >
          {t("copy_message_link")}
        </MenuItem>
        {!!isAdminOrMod && (
          <>
            <MenuDivider />
            <MenuItem onClick={() => handleCopy(id)} icon={<Copy />}>
              {t("copy_message_id")}
            </MenuItem>
            <MenuItem as="a" href={ROUTES.ADMIN_MESSAGE_DETAIL(message.id)} target="_blank" icon={<Shield />}>
              View in admin area
            </MenuItem>
            <MenuItem as="a" href={`/admin/manage_user/${message.user_id}`} target="_blank" icon={<User />}>
              {t("view_user")}
            </MenuItem>
            <MenuItem onClick={handleDelete} icon={<Trash />}>
              {t("common:delete")}
            </MenuItem>
            <MenuItem onClick={handleStop} icon={<Slash />}>
              {t("stop_tree")}
            </MenuItem>
          </>
        )}
      </MenuList>
    </Menu>
  );
};
