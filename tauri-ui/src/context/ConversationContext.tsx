import { createContext, useContext, useReducer, ReactNode } from 'preact/compat'
import {Dispatch} from "preact/compat";

export type Message = {
  role: 'user' | 'assistant' | 'system'
  content: string
}

interface State {
  conversationId: string
  history: Message[]
}

type Action =
  | { type: 'SET_ID'; payload: string }
  | { type: 'SET_HISTORY'; payload: Message[] }
  | { type: 'APPEND_MESSAGE'; payload: Message }

const defaultState: State = {
  conversationId: 'id' + Date.now(),
  history: [],
}

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'SET_ID':
      return { ...state, conversationId: action.payload }
    case 'SET_HISTORY':
      return { ...state, history: action.payload }
    case 'APPEND_MESSAGE':
      return { ...state, history: [...state.history, action.payload] }
    default:
      return state
  }
}

const ConversationContext = createContext<{
  state: State
  dispatch: Dispatch<Action>
} | null>(null)

export const ConversationProvider = ({ children }: { children: ReactNode }) => {
  const [state, dispatch] = useReducer(reducer, defaultState)
  return (
    <ConversationContext.Provider value={{ state, dispatch }}>
      {children}
    </ConversationContext.Provider>
  )
}

export const useConversation = () => {
  const context = useContext(ConversationContext)
  if (!context) throw new Error('useConversation must be used within a ConversationProvider')
  return context
}
