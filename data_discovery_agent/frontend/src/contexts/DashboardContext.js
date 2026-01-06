import React, { createContext, useContext, useReducer, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';

const DashboardContext = createContext();

const initialState = {
  dashboards: [],
  currentDashboard: null,
  widgets: [],
  isLoading: false,
  error: null,
  dataSources: [],
  refreshInterval: 30000, // 30 seconds
};

function dashboardReducer(state, action) {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    case 'SET_DASHBOARDS':
      return { ...state, dashboards: action.payload };
    case 'SET_CURRENT_DASHBOARD':
      return { ...state, currentDashboard: action.payload };
    case 'SET_WIDGETS':
      return { ...state, widgets: action.payload };
    case 'ADD_WIDGET':
      return { ...state, widgets: [...state.widgets, action.payload] };
    case 'UPDATE_WIDGET':
      return {
        ...state,
        widgets: state.widgets.map(widget =>
          widget.id === action.payload.id ? { ...widget, ...action.payload } : widget
        )
      };
    case 'REMOVE_WIDGET':
      return {
        ...state,
        widgets: state.widgets.filter(widget => widget.id !== action.payload)
      };
    case 'SET_DATA_SOURCES':
      return { ...state, dataSources: action.payload };
    case 'SET_ERROR':
      return { ...state, error: action.payload };
    case 'SET_REFRESH_INTERVAL':
      return { ...state, refreshInterval: action.payload };
    default:
      return state;
  }
}

export function DashboardProvider({ children }) {
  const [state, dispatch] = useReducer(dashboardReducer, initialState);

  // Auto-refresh widgets
  useEffect(() => {
    if (state.widgets.length > 0 && state.refreshInterval > 0) {
      const interval = setInterval(() => {
        refreshWidgets();
      }, state.refreshInterval);

      return () => clearInterval(interval);
    }
  }, [state.widgets, state.refreshInterval]);

  const createDashboard = async (dashboardData) => {
    try {
      dispatch({ type: 'SET_LOADING', payload: true });
      const response = await axios.post('/api/dashboards', dashboardData);
      const newDashboard = response.data;
      
      dispatch({ type: 'SET_DASHBOARDS', payload: [...state.dashboards, newDashboard] });
      toast.success('Dashboard created successfully!');
      return newDashboard;
    } catch (error) {
      console.error('Error creating dashboard:', error);
      toast.error('Failed to create dashboard');
      throw error;
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  };

  const loadDashboards = async () => {
    try {
      dispatch({ type: 'SET_LOADING', payload: true });
      const response = await axios.get('/api/dashboards');
      dispatch({ type: 'SET_DASHBOARDS', payload: response.data });
    } catch (error) {
      console.error('Error loading dashboards:', error);
      toast.error('Failed to load dashboards');
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  };

  const loadDashboard = async (dashboardId) => {
    try {
      dispatch({ type: 'SET_LOADING', payload: true });
      const response = await axios.get(`/api/dashboards/${dashboardId}`);
      const dashboard = response.data;
      
      dispatch({ type: 'SET_CURRENT_DASHBOARD', payload: dashboard });
      dispatch({ type: 'SET_WIDGETS', payload: dashboard.widgets || [] });
      
      return dashboard;
    } catch (error) {
      console.error('Error loading dashboard:', error);
      toast.error('Failed to load dashboard');
      throw error;
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  };

  const createWidget = async (widgetData) => {
    try {
      dispatch({ type: 'SET_LOADING', payload: true });
      const response = await axios.post('/api/widgets', widgetData);
      const newWidget = response.data;
      
      dispatch({ type: 'ADD_WIDGET', payload: newWidget });
      toast.success('Widget created successfully!');
      return newWidget;
    } catch (error) {
      console.error('Error creating widget:', error);
      toast.error('Failed to create widget');
      throw error;
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  };

  const updateWidget = async (widgetId, widgetData) => {
    try {
      dispatch({ type: 'SET_LOADING', payload: true });
      const response = await axios.put(`/api/widgets/${widgetId}`, widgetData);
      const updatedWidget = response.data;
      
      dispatch({ type: 'UPDATE_WIDGET', payload: updatedWidget });
      toast.success('Widget updated successfully!');
      return updatedWidget;
    } catch (error) {
      console.error('Error updating widget:', error);
      toast.error('Failed to update widget');
      throw error;
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  };

  const deleteWidget = async (widgetId) => {
    try {
      await axios.delete(`/api/widgets/${widgetId}`);
      dispatch({ type: 'REMOVE_WIDGET', payload: widgetId });
      toast.success('Widget deleted successfully!');
    } catch (error) {
      console.error('Error deleting widget:', error);
      toast.error('Failed to delete widget');
      throw error;
    }
  };

  const refreshWidgets = async () => {
    try {
      const promises = state.widgets.map(async (widget) => {
        try {
          const response = await axios.get(`/api/widgets/${widget.id}/data`);
          return {
            id: widget.id,
            data: response.data,
            lastUpdated: new Date().toISOString(),
          };
        } catch (error) {
          console.error(`Error refreshing widget ${widget.id}:`, error);
          return widget;
        }
      });

      const updatedWidgets = await Promise.all(promises);
      updatedWidgets.forEach(widget => {
        dispatch({ type: 'UPDATE_WIDGET', payload: widget });
      });
    } catch (error) {
      console.error('Error refreshing widgets:', error);
    }
  };

  const getDataSources = async () => {
    try {
      const response = await axios.get('/api/data-sources');
      dispatch({ type: 'SET_DATA_SOURCES', payload: response.data });
    } catch (error) {
      console.error('Error fetching data sources:', error);
    }
  };

  const setRefreshInterval = (interval) => {
    dispatch({ type: 'SET_REFRESH_INTERVAL', payload: interval });
  };

  const value = {
    ...state,
    createDashboard,
    loadDashboards,
    loadDashboard,
    createWidget,
    updateWidget,
    deleteWidget,
    refreshWidgets,
    getDataSources,
    setRefreshInterval,
  };

  return (
    <DashboardContext.Provider value={value}>
      {children}
    </DashboardContext.Provider>
  );
}

export function useDashboard() {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error('useDashboard must be used within a DashboardProvider');
  }
  return context;
} 